// Compute-dense vector add, templated on the element type.
//
//   s     = a[i] + b[i]                       (the "vecadd")
//   x[j]  = s + j                     j < CHAINS independent chains
//   x[j]  = x[j] * m + k   (fused)    repeated `intensity` times per chain
//   c[i]  = sum_j x[j]
//
// CHAINS independent dependency chains give the scheduler enough ILP to keep
// the FMA pipes full, so with a large `intensity` the kernel is bound by the
// FMA rate of the type (FP32 FFMA, FP64 DFMA, INT32 IMAD) and its throughput
// scales with the SM clock. With intensity ~1 it degenerates to a
// bandwidth-bound vecadd, so one binary covers the whole roofline.
//
// m and k are kernel arguments, so the compiler cannot fold the loop.

#ifndef DVFS_FMA_VECADD_CUH
#define DVFS_FMA_VECADD_CUH

#include "common.h"

#include <cstdint>
#include <type_traits>
#include <vector>

constexpr int CHAINS = 8;

__host__ __device__ inline float mad_op(float x, float m, float k) { return fmaf(x, m, k); }
__host__ __device__ inline double mad_op(double x, double m, double k) { return fma(x, m, k); }
__host__ __device__ inline uint32_t mad_op(uint32_t x, uint32_t m, uint32_t k) { return x * m + k; }

template <typename T>
__host__ __device__ inline T fma_element(T a, T b, long intensity, T m, T k) {
  T s = a + b;
  T x[CHAINS];
#pragma unroll
  for (int j = 0; j < CHAINS; ++j) x[j] = s + (T)j;
#pragma unroll 4
  for (long it = 0; it < intensity; ++it) {
#pragma unroll
    for (int j = 0; j < CHAINS; ++j) x[j] = mad_op(x[j], m, k);
  }
  T r = x[0];
#pragma unroll
  for (int j = 1; j < CHAINS; ++j) r = r + x[j];
  return r;
}

template <typename T>
__global__ void fma_vecadd(const T *__restrict__ a, const T *__restrict__ b,
                           T *__restrict__ c, long n, long intensity, T m, T k) {
  long i = blockIdx.x * (long)blockDim.x + threadIdx.x;
  const long stride = (long)gridDim.x * blockDim.x;
  for (; i < n; i += stride) c[i] = fma_element<T>(a[i], b[i], intensity, m, k);
}

// Shared main for the FP32 / FP64 / INT32 binaries.
//   default_intensity: chosen so the kernel is firmly compute bound.
template <typename T>
int fma_vecadd_main(int argc, char **argv, const char *name, const char *unit,
                    long default_intensity, T m, T k) {
  const double seconds = arg_double(argc, argv, 1, 20.0);
  const long intensity = (long)arg_double(argc, argv, 2, (double)default_intensity);
  const long n = (long)arg_double(argc, argv, 3, (double)(1L << 24));
  CUDA_CHECK(cudaSetDevice((int)env_double("DVFS_DEVICE", 0)));

  std::vector<T> h_a(n), h_b(n);
  for (long i = 0; i < n; ++i) {
    h_a[i] = (T)(i % 1024) / (T)1024;   // integer types: 0, fine
    h_b[i] = (T)1 + (T)(i % 7);
  }
  T *d_a, *d_b, *d_c;
  const size_t bytes = (size_t)n * sizeof(T);
  CUDA_CHECK(cudaMalloc(&d_a, bytes));
  CUDA_CHECK(cudaMalloc(&d_b, bytes));
  CUDA_CHECK(cudaMalloc(&d_c, bytes));
  CUDA_CHECK(cudaMemcpy(d_a, h_a.data(), bytes, cudaMemcpyHostToDevice));
  CUDA_CHECK(cudaMemcpy(d_b, h_b.data(), bytes, cudaMemcpyHostToDevice));

  const int threads = 256;
  const int blocks = full_grid(fma_vecadd<T>, threads);

  BenchConfig cfg;
  cfg.name = name;
  cfg.op_unit = unit;
  cfg.seconds = seconds;
  cfg.intensity = intensity;
  cfg.n = n;
  // 1 add + CHAINS init adds + 2 ops per FMA + (CHAINS-1) reduction adds
  cfg.ops_per_pass = (double)n * (1 + CHAINS + 2.0 * CHAINS * intensity + (CHAINS - 1));
  cfg.bytes_per_pass = 3.0 * bytes;

  auto launch = [&] {
    fma_vecadd<T><<<blocks, threads>>>(d_a, d_b, d_c, n, intensity, m, k);
  };
  auto verify = [&](double &checksum) {
    CUDA_CHECK(cudaDeviceSynchronize());
    std::vector<T> h_c(n);
    CUDA_CHECK(cudaMemcpy(h_c.data(), d_c, bytes, cudaMemcpyDeviceToHost));
    bool ok = true;
    const long probe[] = {0, 1, n / 3, n / 2, n - 1};
    checksum = 0;
    for (long i : probe) {
      const T ref = fma_element<T>(h_a[i], h_b[i], intensity, m, k);
      const double got = (double)h_c[i], want = (double)ref;
      checksum += got;
      const double tol = std::is_integral<T>::value ? 0.0 : 1e-4 * std::fabs(want) + 1e-6;
      if (!(std::fabs(got - want) <= tol)) {
        std::fprintf(stderr, "[%s] mismatch at %ld: got %.9g want %.9g\n", name, i, got, want);
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

#endif  // DVFS_FMA_VECADD_CUH
