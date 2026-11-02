// vecadd_fp16 -- packed half2 vector add followed by `intensity` HFMA2 per
// chain (4 flops per instruction). Highest non-tensor flop rate and typically
// the highest power density of the CUDA-core kernels.
//
// Each element of a/b/c is one __half2 (two halves). Values can stagnate in
// half precision (the update falls below half an ulp), which does not matter
// here: the HFMA2 instructions still execute. Verification therefore only
// checks the result is finite and in range.
//
// Usage: ./bin/vecadd_fp16 [seconds=20] [intensity=512] [n=16777216]

#include "common.h"

#include <cuda_fp16.h>
#include <vector>

constexpr int CHAINS = 8;

__global__ void vecadd_fp16(const __half2 *__restrict__ a,
                            const __half2 *__restrict__ b,
                            __half2 *__restrict__ c, long n, long intensity,
                            __half2 m, __half2 k) {
  long i = blockIdx.x * (long)blockDim.x + threadIdx.x;
  const long stride = (long)gridDim.x * blockDim.x;
  for (; i < n; i += stride) {
    const __half2 s = __hadd2(a[i], b[i]);
    __half2 x[CHAINS];
#pragma unroll
    for (int j = 0; j < CHAINS; ++j)
      x[j] = __hadd2(s, __float2half2_rn(0.125f * j));
#pragma unroll 4
    for (long it = 0; it < intensity; ++it) {
#pragma unroll
      for (int j = 0; j < CHAINS; ++j) x[j] = __hfma2(x[j], m, k);
    }
    __half2 r = x[0];
#pragma unroll
    for (int j = 1; j < CHAINS; ++j) r = __hadd2(r, x[j]);
    c[i] = r;
  }
}

int main(int argc, char **argv) {
  const double seconds = arg_double(argc, argv, 1, 20.0);
  const long intensity = (long)arg_double(argc, argv, 2, 512);
  const long n = (long)arg_double(argc, argv, 3, (double)(1L << 24));
  CUDA_CHECK(cudaSetDevice((int)env_double("DVFS_DEVICE", 0)));

  std::vector<__half2> h_a(n), h_b(n);
  for (long i = 0; i < n; ++i) {
    h_a[i] = __floats2half2_rn((i % 64) / 64.0f, (i % 32) / 32.0f);
    h_b[i] = __floats2half2_rn(1.0f, 0.5f);
  }
  const size_t bytes = (size_t)n * sizeof(__half2);
  __half2 *d_a, *d_b, *d_c;
  CUDA_CHECK(cudaMalloc(&d_a, bytes));
  CUDA_CHECK(cudaMalloc(&d_b, bytes));
  CUDA_CHECK(cudaMalloc(&d_c, bytes));
  CUDA_CHECK(cudaMemcpy(d_a, h_a.data(), bytes, cudaMemcpyHostToDevice));
  CUDA_CHECK(cudaMemcpy(d_b, h_b.data(), bytes, cudaMemcpyHostToDevice));

  const int threads = 256;
  const int blocks = full_grid(vecadd_fp16, threads);
  const __half2 m = __floats2half2_rn(0.999f, 0.999f);
  const __half2 k = __floats2half2_rn(0.001f, 0.001f);

  BenchConfig cfg;
  cfg.name = "vecadd_fp16";
  cfg.op_unit = "FP16flop";
  cfg.seconds = seconds;
  cfg.intensity = intensity;
  cfg.n = n;
  // per half2 element: 2 lanes x (1 + CHAINS + 2*CHAINS*intensity + CHAINS-1)
  cfg.ops_per_pass = 2.0 * n * (1 + CHAINS + 2.0 * CHAINS * intensity + (CHAINS - 1));
  cfg.bytes_per_pass = 3.0 * bytes;

  auto launch = [&] {
    vecadd_fp16<<<blocks, threads>>>(d_a, d_b, d_c, n, intensity, m, k);
  };
  auto verify = [&](double &checksum) {
    CUDA_CHECK(cudaDeviceSynchronize());
    std::vector<__half2> h_c(n);
    CUDA_CHECK(cudaMemcpy(h_c.data(), d_c, bytes, cudaMemcpyDeviceToHost));
    bool ok = true;
    checksum = 0;
    const long probe[] = {0, 1, n / 3, n / 2, n - 1};
    for (long i : probe) {
      const float2 v = __half22float2(h_c[i]);
      checksum += v.x + v.y;
      if (!std::isfinite(v.x) || !std::isfinite(v.y) || v.x <= 0 || v.y <= 0 ||
          v.x > 1000 || v.y > 1000) {
        std::fprintf(stderr, "[vecadd_fp16] bad value at %ld: %g %g\n", i, v.x, v.y);
        ok = false;
      }
    }
    return ok;
  };

  const int rc = run_bench(cfg, launch, verify);
  CUDA_CHECK(cudaFree(d_a));
  CUDA_CHECK(cudaFree(d_b));
  CUDA_CHECK(cudaFree(d_c));
  return rc;
}
