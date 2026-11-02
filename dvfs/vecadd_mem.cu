// vecadd_mem -- plain c = a + b over vectors much larger than L2.
//
// The memory-bound reference point: its throughput should barely move when
// the SM clock is lowered (HBM bandwidth limits it), so it shows how much
// power DVFS can save for free on bandwidth-bound code. float4 loads keep it
// at the HBM roofline.
//
// Usage: ./bin/vecadd_mem [seconds=20] [unused=1] [n=268435456]
//   n is the float count per vector (default 1 GiB per vector, 3 GiB total).

#include "common.h"

#include <vector>

__global__ void vecadd_mem(const float4 *__restrict__ a,
                           const float4 *__restrict__ b,
                           float4 *__restrict__ c, long n4) {
  long i = blockIdx.x * (long)blockDim.x + threadIdx.x;
  const long stride = (long)gridDim.x * blockDim.x;
  for (; i < n4; i += stride) {
    const float4 x = a[i], y = b[i];
    c[i] = make_float4(x.x + y.x, x.y + y.y, x.z + y.z, x.w + y.w);
  }
}

int main(int argc, char **argv) {
  const double seconds = arg_double(argc, argv, 1, 20.0);
  long n = (long)arg_double(argc, argv, 3, (double)(1L << 28));
  n = (n + 3) / 4 * 4;
  const long n4 = n / 4;
  CUDA_CHECK(cudaSetDevice((int)env_double("DVFS_DEVICE", 0)));

  const size_t bytes = (size_t)n * sizeof(float);
  std::vector<float> h(n);
  for (long i = 0; i < n; ++i) h[i] = (float)(i % 1000);
  float *d_a, *d_b, *d_c;
  CUDA_CHECK(cudaMalloc(&d_a, bytes));
  CUDA_CHECK(cudaMalloc(&d_b, bytes));
  CUDA_CHECK(cudaMalloc(&d_c, bytes));
  CUDA_CHECK(cudaMemcpy(d_a, h.data(), bytes, cudaMemcpyHostToDevice));
  CUDA_CHECK(cudaMemcpy(d_b, h.data(), bytes, cudaMemcpyHostToDevice));

  const int threads = 256;
  const int blocks = full_grid(vecadd_mem, threads);

  BenchConfig cfg;
  cfg.name = "vecadd_mem";
  cfg.op_unit = "FP32flop";
  cfg.seconds = seconds;
  cfg.intensity = 1;
  cfg.n = n;
  cfg.ops_per_pass = (double)n;
  cfg.bytes_per_pass = 3.0 * bytes;

  auto launch = [&] {
    vecadd_mem<<<blocks, threads>>>((const float4 *)d_a, (const float4 *)d_b,
                                    (float4 *)d_c, n4);
  };
  auto verify = [&](double &checksum) {
    CUDA_CHECK(cudaDeviceSynchronize());
    CUDA_CHECK(cudaMemcpy(h.data(), d_c, bytes, cudaMemcpyDeviceToHost));
    bool ok = true;
    checksum = 0;
    const long probe[] = {0, 1, n / 3, n / 2, n - 1};
    for (long i : probe) {
      const float want = 2.0f * (float)(i % 1000);
      checksum += h[i];
      if (h[i] != want) {
        std::fprintf(stderr, "[vecadd_mem] mismatch at %ld: %g vs %g\n", i, h[i], want);
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
