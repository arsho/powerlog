// reduction -- parallel sum reduction with shared memory (latency bound).
//
// A tree reduction with sequential addressing plus a grid-stride load, i.e. the
// standard high-throughput formulation. Reductions are synchronization heavy,
// which shows up as a distinct power profile from matmul or vecadd.
//
// Usage: ./reduction [n_elements] [iterations]

#include "gpu_common.h"

#define BLOCK 256

__global__ void reduce_sum(const float *input, float *partial, long n) {
  __shared__ float scratch[BLOCK];
  const unsigned tid = threadIdx.x;

  // Grid-stride accumulation before the in-block tree reduction.
  float sum = 0.0f;
  for (long i = blockIdx.x * (long)blockDim.x + tid;
       i < n; i += (long)gridDim.x * blockDim.x) {
    sum += input[i];
  }
  scratch[tid] = sum;
  __syncthreads();

  for (unsigned stride = blockDim.x / 2; stride > 0; stride >>= 1) {
    if (tid < stride) scratch[tid] += scratch[tid + stride];
    __syncthreads();
  }

  if (tid == 0) partial[blockIdx.x] = scratch[0];
}

int main(int argc, char **argv) {
  const long n = arg_or(argc, argv, 1, 1L << 26);   // 64 Mi elements
  const long iterations = arg_or(argc, argv, 2, 300);
  print_header("reduction", n, iterations);

  const int blocks = 1024;
  const size_t bytes = (size_t)n * sizeof(float);
  float *h_in = (float *)std::malloc(bytes);
  for (long i = 0; i < n; ++i) h_in[i] = 1.0f;

  float *d_in, *d_partial;
  GPU_CHECK(gpuMalloc(&d_in, bytes));
  GPU_CHECK(gpuMalloc(&d_partial, blocks * sizeof(float)));
  GPU_CHECK(gpuMemcpy(d_in, h_in, bytes, gpuMemcpyHostToDevice));

  for (long it = 0; it < iterations; ++it) {
    reduce_sum<<<blocks, BLOCK>>>(d_in, d_partial, n);
  }
  GPU_CHECK_KERNEL();

  // Final stage on the host: only `blocks` values remain.
  float *h_partial = (float *)std::malloc(blocks * sizeof(float));
  GPU_CHECK(gpuMemcpy(h_partial, d_partial, blocks * sizeof(float),
                      gpuMemcpyDeviceToHost));
  double total = 0.0;
  for (int i = 0; i < blocks; ++i) total += h_partial[i];

  const bool ok = std::fabs(total - (double)n) / (double)n < 1e-4;
  print_footer("reduction", total, ok);

  GPU_CHECK(gpuFree(d_in));
  GPU_CHECK(gpuFree(d_partial));
  std::free(h_in);
  std::free(h_partial);
  return ok ? 0 : 1;
}
