// Shared harness for the DVFS / power-control micro-benchmarks.
//
// Every benchmark is a vecadd-shaped kernel (read a[i], b[i]; write c[i]) whose
// arithmetic per element is tunable, so the same code walks from memory bound
// to compute bound. The harness:
//   * runs the kernel for a fixed wall time (not a fixed iteration count), so
//     every operating point is measured over the same window;
//   * samples NVML in a background thread: GPU power, module power (Grace
//     Blackwell: GPU + CPU + memory, if exposed), SM and memory clocks,
//     temperature, and the clock-event (throttle) reasons;
//   * reads the NVML energy counter before/after for an exact GPU energy;
//   * prints a human summary and one machine-readable "CSV," row.
//
// Positional args (all optional):  <bin> [seconds] [intensity] [n_elements]
// Environment:
//   DVFS_WARMUP     warm-up seconds before measuring (default 3)
//   DVFS_SAMPLE_MS  NVML sampling period in ms (default 20)
//   DVFS_TRACE      path: write the per-sample trace there as CSV
//   DVFS_TAG        free-form label copied into the CSV row (e.g. "lgc=1500")
//   DVFS_DEVICE     CUDA device ordinal (default 0)

#ifndef DVFS_COMMON_H
#define DVFS_COMMON_H

#include <cuda_runtime.h>
#include <nvml.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>

#define CUDA_CHECK(call)                                                       \
  do {                                                                         \
    cudaError_t _e = (call);                                                   \
    if (_e != cudaSuccess) {                                                   \
      std::fprintf(stderr, "%s:%d: CUDA error: %s\n", __FILE__, __LINE__,      \
                   cudaGetErrorString(_e));                                    \
      std::exit(EXIT_FAILURE);                                                 \
    }                                                                          \
  } while (0)

// NVML failures are reported but never fatal: the benchmark still runs and
// reports performance even where telemetry is restricted.
static inline bool nvml_ok(nvmlReturn_t r, const char *what) {
  if (r == NVML_SUCCESS) return true;
  std::fprintf(stderr, "[nvml] %s: %s\n", what, nvmlErrorString(r));
  return false;
}

static inline double env_double(const char *name, double fallback) {
  const char *s = std::getenv(name);
  if (!s || !*s) return fallback;
  char *end = nullptr;
  double v = std::strtod(s, &end);
  return (end == s) ? fallback : v;
}

static inline double arg_double(int argc, char **argv, int i, double fallback) {
  if (i >= argc) return fallback;
  char *end = nullptr;
  double v = std::strtod(argv[i], &end);
  return (end == argv[i] || v <= 0) ? fallback : v;
}

static inline double now_s() {
  using namespace std::chrono;
  return duration<double>(steady_clock::now().time_since_epoch()).count();
}

// Clock-event ("throttle") reason bits. Numeric values are stable across NVML
// versions; the macro names changed (Throttle -> Event), so they are spelled
// out here.
enum : unsigned long long {
  REASON_IDLE = 0x1ULL,
  REASON_CLOCK_SETTING = 0x2ULL,   // applications / locked clocks
  REASON_SW_POWER_CAP = 0x4ULL,
  REASON_HW_SLOWDOWN = 0x8ULL,
  REASON_SYNC_BOOST = 0x10ULL,
  REASON_SW_THERMAL = 0x20ULL,
  REASON_HW_THERMAL = 0x40ULL,
  REASON_HW_POWER_BRAKE = 0x80ULL,
};

static inline std::string reasons_str(unsigned long long r) {
  std::string s;
  auto add = [&](unsigned long long bit, const char *name) {
    if (r & bit) { if (!s.empty()) s += '|'; s += name; }
  };
  add(REASON_IDLE, "idle");
  add(REASON_CLOCK_SETTING, "clk_setting");
  add(REASON_SW_POWER_CAP, "sw_pwr_cap");
  add(REASON_HW_SLOWDOWN, "hw_slowdown");
  add(REASON_SYNC_BOOST, "sync_boost");
  add(REASON_SW_THERMAL, "sw_thermal");
  add(REASON_HW_THERMAL, "hw_thermal");
  add(REASON_HW_POWER_BRAKE, "hw_pwr_brake");
  return s.empty() ? "none" : s;
}

// ---------------------------------------------------------------------------
// NVML sampler
// ---------------------------------------------------------------------------
struct Sampler {
  nvmlDevice_t dev{};
  bool have_dev = false;
  bool have_energy = false;
  bool have_instant = false;   // NVML_FI_DEV_POWER_INSTANT (GPU scope)
  bool have_module = false;    // NVML_FI_DEV_POWER_INSTANT (module scope)
  double period_s = 0.02;
  FILE *trace = nullptr;

  std::atomic<bool> stop{false};
  std::thread th;

  // accumulators (owned by the sampler thread until join)
  long n = 0;
  double t0 = 0, t_last = 0;
  double sum_p = 0, max_p = 0, sum_mod = 0, max_mod = 0, int_p = 0, int_mod = 0;
  double sum_sm = 0, sum_mem = 0;
  unsigned min_sm = ~0u, max_sm = 0, max_temp = 0;
  unsigned long long reasons_or = 0;
  long cnt_pwrcap = 0, cnt_thermal = 0, cnt_hwslow = 0, cnt_clkset = 0;
  unsigned long long e0_mj = 0, e1_mj = 0;

  // static info
  char name[NVML_DEVICE_NAME_BUFFER_SIZE] = "unknown";
  unsigned limit_mw = 0, default_limit_mw = 0, min_limit_mw = 0, max_limit_mw = 0;
  unsigned max_sm_mhz = 0, max_mem_mhz = 0;

  bool init(int cuda_dev) {
    if (!nvml_ok(nvmlInit_v2(), "nvmlInit")) return false;

    // Map the CUDA ordinal to the NVML handle by UUID (orderings can differ).
    cudaDeviceProp prop{};
    CUDA_CHECK(cudaGetDeviceProperties(&prop, cuda_dev));
    char want[64];
    const unsigned char *u = (const unsigned char *)prop.uuid.bytes;
    std::snprintf(want, sizeof(want),
                  "GPU-%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-"
                  "%02x%02x%02x%02x%02x%02x",
                  u[0], u[1], u[2], u[3], u[4], u[5], u[6], u[7], u[8], u[9],
                  u[10], u[11], u[12], u[13], u[14], u[15]);
    unsigned count = 0;
    nvmlDeviceGetCount_v2(&count);
    for (unsigned i = 0; i < count && !have_dev; ++i) {
      nvmlDevice_t d;
      char uuid[96];
      if (nvmlDeviceGetHandleByIndex_v2(i, &d) != NVML_SUCCESS) continue;
      if (nvmlDeviceGetUUID(d, uuid, sizeof(uuid)) != NVML_SUCCESS) continue;
      if (std::strcmp(uuid, want) == 0) { dev = d; have_dev = true; }
    }
    if (!have_dev && count > 0 &&
        nvmlDeviceGetHandleByIndex_v2(0, &dev) == NVML_SUCCESS) {
      std::fprintf(stderr, "[nvml] UUID match failed; using NVML index 0\n");
      have_dev = true;
    }
    if (!have_dev) return false;

    nvmlDeviceGetName(dev, name, sizeof(name));
    nvmlDeviceGetEnforcedPowerLimit(dev, &limit_mw);
    nvmlDeviceGetPowerManagementDefaultLimit(dev, &default_limit_mw);
    nvmlDeviceGetPowerManagementLimitConstraints(dev, &min_limit_mw, &max_limit_mw);
    nvmlDeviceGetMaxClockInfo(dev, NVML_CLOCK_SM, &max_sm_mhz);
    nvmlDeviceGetMaxClockInfo(dev, NVML_CLOCK_MEM, &max_mem_mhz);

    unsigned long long e;
    have_energy = nvmlDeviceGetTotalEnergyConsumption(dev, &e) == NVML_SUCCESS;
    double tmp;
    have_instant = read_power_field(0, &tmp);
    have_module = read_power_field(1, &tmp);
    return true;
  }

  // scope 0 = GPU, 1 = module (Grace Blackwell / Grace Hopper superchip).
  bool read_power_field(unsigned scope, double *watts) {
#if defined(NVML_FI_DEV_POWER_INSTANT)
    nvmlFieldValue_t fv;
    std::memset(&fv, 0, sizeof(fv));
    fv.fieldId = NVML_FI_DEV_POWER_INSTANT;
    fv.scopeId = scope;
    if (nvmlDeviceGetFieldValues(dev, 1, &fv) != NVML_SUCCESS) return false;
    if (fv.nvmlReturn != NVML_SUCCESS) return false;
    double mw;
    switch (fv.valueType) {
      case NVML_VALUE_TYPE_UNSIGNED_INT: mw = fv.value.uiVal; break;
      case NVML_VALUE_TYPE_UNSIGNED_LONG: mw = (double)fv.value.ulVal; break;
      case NVML_VALUE_TYPE_UNSIGNED_LONG_LONG: mw = (double)fv.value.ullVal; break;
      case NVML_VALUE_TYPE_SIGNED_LONG_LONG: mw = (double)fv.value.sllVal; break;
      case NVML_VALUE_TYPE_DOUBLE: mw = fv.value.dVal; break;
      default: return false;
    }
    if (mw <= 0) return false;
    *watts = mw / 1000.0;
    return true;
#else
    (void)scope; (void)watts;
    return false;
#endif
  }

  unsigned long long read_reasons() {
    unsigned long long r = 0;
#if defined(nvmlClocksEventReasonGpuIdle)
    nvmlDeviceGetCurrentClocksEventReasons(dev, &r);
#else
    nvmlDeviceGetCurrentClocksThrottleReasons(dev, &r);
#endif
    return r;
  }

  void sample_once() {
    double t = now_s() - t0;
    double p = 0, pm = 0;
    if (!(have_instant && read_power_field(0, &p))) {
      unsigned mw = 0;
      nvmlDeviceGetPowerUsage(dev, &mw);   // may be a ~1 s moving average
      p = mw / 1000.0;
    }
    if (have_module) read_power_field(1, &pm);
    unsigned sm = 0, mem = 0, temp = 0;
    nvmlDeviceGetClockInfo(dev, NVML_CLOCK_SM, &sm);
    nvmlDeviceGetClockInfo(dev, NVML_CLOCK_MEM, &mem);
    nvmlDeviceGetTemperature(dev, NVML_TEMPERATURE_GPU, &temp);
    unsigned long long r = read_reasons();

    if (n > 0) {   // right Riemann sum, same convention as powerlog
      int_p += p * (t - t_last);
      int_mod += pm * (t - t_last);
    }
    t_last = t;
    ++n;
    sum_p += p; if (p > max_p) max_p = p;
    sum_mod += pm; if (pm > max_mod) max_mod = pm;
    sum_sm += sm; sum_mem += mem;
    if (sm < min_sm) min_sm = sm;
    if (sm > max_sm) max_sm = sm;
    if (temp > max_temp) max_temp = temp;
    reasons_or |= r;
    if (r & REASON_SW_POWER_CAP) ++cnt_pwrcap;
    if (r & (REASON_SW_THERMAL | REASON_HW_THERMAL)) ++cnt_thermal;
    if (r & (REASON_HW_SLOWDOWN | REASON_HW_POWER_BRAKE)) ++cnt_hwslow;
    if (r & REASON_CLOCK_SETTING) ++cnt_clkset;
    if (trace)
      std::fprintf(trace, "%.4f,%.2f,%.2f,%u,%u,%u,0x%llx\n", t, p, pm, sm,
                   mem, temp, r);
  }

  void start(double period, const char *trace_path) {
    period_s = period;
    if (trace_path && *trace_path) {
      trace = std::fopen(trace_path, "w");
      if (trace)
        std::fprintf(trace,
                     "t_s,gpu_power_w,module_power_w,sm_mhz,mem_mhz,temp_c,"
                     "reasons\n");
    }
    if (!have_dev) return;
    if (have_energy) nvmlDeviceGetTotalEnergyConsumption(dev, &e0_mj);
    t0 = now_s();
    th = std::thread([this] {
      double next = now_s();
      while (!stop.load(std::memory_order_relaxed)) {
        sample_once();
        next += period_s;
        double wait = next - now_s();
        if (wait > 0)
          std::this_thread::sleep_for(std::chrono::duration<double>(wait));
        else
          next = now_s();
      }
    });
  }

  void finish() {
    if (!have_dev) return;
    stop = true;
    th.join();
    sample_once();   // closing sample
    if (have_energy) nvmlDeviceGetTotalEnergyConsumption(dev, &e1_mj);
    if (trace) std::fclose(trace);
  }

  double energy_j() const {
    if (have_energy && e1_mj > e0_mj) return (e1_mj - e0_mj) / 1000.0;
    return int_p;
  }
  double frac(long c) const { return n ? (double)c / n : 0.0; }
};

// ---------------------------------------------------------------------------
// Benchmark driver
// ---------------------------------------------------------------------------
struct BenchConfig {
  const char *name;        // kernel name, e.g. "vecadd_fp32"
  const char *op_unit;     // what "ops" counts, e.g. "FP32 flop"
  double seconds;          // measured window
  long intensity;          // inner-loop trip count (work per element)
  long n;                  // elements
  double ops_per_pass;     // arithmetic ops per kernel launch
  double bytes_per_pass;   // DRAM bytes per kernel launch (compulsory)
};

// launch(): enqueue one pass on the default stream (no sync).
// verify(checksum&): sync, copy back, return pass/fail and a checksum.
template <typename Launch, typename Verify>
int run_bench(const BenchConfig &cfg, Launch launch, Verify verify) {
  const int cuda_dev = (int)env_double("DVFS_DEVICE", 0);
  const double warmup = env_double("DVFS_WARMUP", 3.0);
  const double period = env_double("DVFS_SAMPLE_MS", 20.0) / 1000.0;
  const char *tag = std::getenv("DVFS_TAG");
  if (!tag || !*tag) tag = "-";

  Sampler s;
  s.init(cuda_dev);

  // -- warm-up: also measures a single pass to size the launch batches -------
  cudaEvent_t e_a, e_b;
  CUDA_CHECK(cudaEventCreate(&e_a));
  CUDA_CHECK(cudaEventCreate(&e_b));
  launch();
  CUDA_CHECK(cudaGetLastError());
  CUDA_CHECK(cudaDeviceSynchronize());
  CUDA_CHECK(cudaEventRecord(e_a));
  launch();
  CUDA_CHECK(cudaEventRecord(e_b));
  CUDA_CHECK(cudaEventSynchronize(e_b));
  float pass_ms = 0;
  CUDA_CHECK(cudaEventElapsedTime(&pass_ms, e_a, e_b));
  // ~50 ms of work per batch keeps sync overhead negligible.
  long batch = (long)std::ceil(50.0 / std::max(pass_ms, 1e-3f));
  if (batch < 1) batch = 1;

  for (double t_end = now_s() + warmup; now_s() < t_end;) {
    for (long j = 0; j < batch; ++j) launch();
    CUDA_CHECK(cudaDeviceSynchronize());
  }

  // -- measured window --------------------------------------------------------
  // Keep two batches in flight so the GPU never idles while the host checks
  // the clock.
  cudaEvent_t start, stop, prev;
  CUDA_CHECK(cudaEventCreate(&start));
  CUDA_CHECK(cudaEventCreate(&stop));
  CUDA_CHECK(cudaEventCreate(&prev));
  s.start(period, std::getenv("DVFS_TRACE"));
  const double t_begin = now_s();
  CUDA_CHECK(cudaEventRecord(start));
  long iters = 0;
  bool first = true;
  while (true) {
    for (long j = 0; j < batch; ++j) launch();
    iters += batch;
    if (!first) CUDA_CHECK(cudaEventSynchronize(prev));
    CUDA_CHECK(cudaEventRecord(prev));
    first = false;
    if (now_s() - t_begin >= cfg.seconds) break;
  }
  CUDA_CHECK(cudaEventRecord(stop));
  CUDA_CHECK(cudaEventSynchronize(stop));
  CUDA_CHECK(cudaGetLastError());
  s.finish();

  float ms = 0;
  CUDA_CHECK(cudaEventElapsedTime(&ms, start, stop));
  const double t = ms / 1000.0;
  double checksum = 0;
  const bool ok = verify(checksum);

  const double gops = cfg.ops_per_pass * iters / t / 1e9;
  const double gbps = cfg.bytes_per_pass * iters / t / 1e9;
  const double energy = s.energy_j();
  const double avg_p = s.n ? s.sum_p / s.n : 0;
  const double avg_pm = s.n ? s.sum_mod / s.n : 0;
  const double pwr = t > 0 ? energy / t : 0;   // energy-based average power
  const double avg_sm = s.n ? s.sum_sm / s.n : 0;
  const double avg_mem = s.n ? s.sum_mem / s.n : 0;
  const double gops_per_w = pwr > 0 ? gops / pwr : 0;
  const double ai = cfg.bytes_per_pass > 0 ? cfg.ops_per_pass / cfg.bytes_per_pass : 0;

  std::printf("================================================================\n");
  std::printf("[%s] %s  tag=%s\n", cfg.name, s.name, tag);
  std::printf("  n=%ld  intensity=%ld  AI=%.2f op/B  pass=%.3f ms  iters=%ld  time=%.3f s\n",
              cfg.n, cfg.intensity, ai, t * 1000.0 / iters, iters, t);
  std::printf("  throughput   %10.1f G%s/s   %8.1f GB/s\n", gops, cfg.op_unit, gbps);
  std::printf("  GPU power    avg %7.1f W  (sampled %.1f, max %.1f)  limit %.0f W [%.0f..%.0f, default %.0f]\n",
              pwr, avg_p, s.max_p, s.limit_mw / 1000.0, s.min_limit_mw / 1000.0,
              s.max_limit_mw / 1000.0, s.default_limit_mw / 1000.0);
  if (s.have_module)
    std::printf("  module power avg %7.1f W  (max %.1f)  energy %.1f J\n", avg_pm,
                s.max_mod, s.int_mod);
  std::printf("  GPU energy   %10.1f J  (%s)   efficiency %.2f G%s/s/W\n", energy,
              s.have_energy ? "NVML counter" : "integrated samples", gops_per_w,
              cfg.op_unit);
  std::printf("  SM clock     avg %6.0f MHz  [%u..%u], max %u   mem clock avg %.0f MHz\n",
              avg_sm, s.min_sm == ~0u ? 0 : s.min_sm, s.max_sm, s.max_sm_mhz, avg_mem);
  std::printf("  temp max %u C   reasons seen: %s\n", s.max_temp,
              reasons_str(s.reasons_or).c_str());
  std::printf("  sample fraction: pwr_cap %.2f  thermal %.2f  hw_slowdown %.2f  clk_setting %.2f  (%ld samples)\n",
              s.frac(s.cnt_pwrcap), s.frac(s.cnt_thermal), s.frac(s.cnt_hwslow),
              s.frac(s.cnt_clkset), s.n);
  std::printf("  checksum %.6g  verification %s\n", checksum, ok ? "PASS" : "FAIL");

  std::printf(
      "CSVHDR,kernel,tag,intensity,n,ai_op_per_byte,iters,time_s,gops,gbps,"
      "gpu_power_w,gpu_power_sampled_w,gpu_power_max_w,gpu_energy_j,"
      "module_power_w,module_power_max_w,gops_per_w,energy_per_pass_mj,"
      "sm_mhz_avg,sm_mhz_min,sm_mhz_max,mem_mhz_avg,temp_max_c,"
      "power_limit_w,frac_pwr_cap,frac_thermal,frac_hw_slowdown,"
      "frac_clk_setting,reasons,verify\n");
  std::printf(
      "CSV,%s,%s,%ld,%ld,%.4f,%ld,%.4f,%.2f,%.2f,%.2f,%.2f,%.2f,%.3f,%.2f,"
      "%.2f,%.4f,%.4f,%.1f,%u,%u,%.1f,%u,%.1f,%.3f,%.3f,%.3f,%.3f,%s,%s\n",
      cfg.name, tag, cfg.intensity, cfg.n, ai, iters, t, gops, gbps, pwr, avg_p,
      s.max_p, energy, avg_pm, s.max_mod, gops_per_w,
      iters ? energy / iters * 1000.0 : 0, avg_sm,
      s.min_sm == ~0u ? 0 : s.min_sm, s.max_sm, avg_mem, s.max_temp,
      s.limit_mw / 1000.0, s.frac(s.cnt_pwrcap), s.frac(s.cnt_thermal),
      s.frac(s.cnt_hwslow), s.frac(s.cnt_clkset),
      reasons_str(s.reasons_or).c_str(), ok ? "PASS" : "FAIL");

  if (s.have_dev) nvmlShutdown();
  return ok ? 0 : 1;
}

// Grid sized to fill the GPU exactly once (grid-stride loops do the rest).
template <typename K>
static inline int full_grid(K kernel, int threads) {
  int dev = 0, sms = 0, per_sm = 0;
  CUDA_CHECK(cudaGetDevice(&dev));
  CUDA_CHECK(cudaDeviceGetAttribute(&sms, cudaDevAttrMultiProcessorCount, dev));
  CUDA_CHECK(cudaOccupancyMaxActiveBlocksPerMultiprocessor(&per_sm, kernel, threads, 0));
  return sms * (per_sm > 0 ? per_sm : 1);
}

#endif  // DVFS_COMMON_H
