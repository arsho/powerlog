// vecadd -- element-wise vector addition (memory-bandwidth bound).
//
// A deliberately simple, bandwidth-limited kernel: useful as the low-intensity
// end of the spectrum when comparing energy per unit of work.
//
// Usage: ./vecadd [n_elements] [iterations]

#include "gpu_common.h"

__global__ void vecadd(const float *a, const float *b, float *c, long n) {
  long i = blockIdx.x * (long)blockDim.x + threadIdx.x;
  long stride = (long)gridDim.x * blockDim.x;
  for (; i < n; i += stride) {
    c[i] = a[i] + b[i];
  }
}

int main(int argc, char **argv) {
  const long n = arg_or(argc, argv, 1, 1L << 26);   // 64 Mi elements
  const long iterations = arg_or(argc, argv, 2, 200);
  print_header("vecadd", n, iterations);

  const size_t bytes = (size_t)n * sizeof(float);
  float *h_a = (float *)std::malloc(bytes);
  float *h_c = (float *)std::malloc(bytes);
  for (long i = 0; i < n; ++i) h_a[i] = 1.0f;

  float *d_a, *d_b, *d_c;
  GPU_CHECK(gpuMalloc(&d_a, bytes));
  GPU_CHECK(gpuMalloc(&d_b, bytes));
  GPU_CHECK(gpuMalloc(&d_c, bytes));
  GPU_CHECK(gpuMemcpy(d_a, h_a, bytes, gpuMemcpyHostToDevice));
  GPU_CHECK(gpuMemcpy(d_b, h_a, bytes, gpuMemcpyHostToDevice));

  const int threads = 256;
  const int blocks = 1024;
  for (long it = 0; it < iterations; ++it) {
    vecadd<<<blocks, threads>>>(d_a, d_b, d_c, n);
  }
  GPU_CHECK_KERNEL();

  GPU_CHECK(gpuMemcpy(h_c, d_c, bytes, gpuMemcpyDeviceToHost));
  const bool ok = std::fabs(h_c[0] - 2.0f) < 1e-5f &&
                  std::fabs(h_c[n - 1] - 2.0f) < 1e-5f;
  print_footer("vecadd", h_c[0], ok);

  GPU_CHECK(gpuFree(d_a));
  GPU_CHECK(gpuFree(d_b));
  GPU_CHECK(gpuFree(d_c));
  std::free(h_a);
  std::free(h_c);
  return ok ? 0 : 1;
}
