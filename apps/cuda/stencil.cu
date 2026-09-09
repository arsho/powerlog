// stencil -- 2D five-point Jacobi heat diffusion (memory bound, iterative).
//
// Representative of structured-grid PDE solvers: a long sequence of short
// kernels with a device-side ping-pong buffer swap. The steady, repetitive power
// profile contrasts with the bursty behaviour of one-shot kernels.
//
// Usage: ./stencil [grid_dim] [iterations]

#include "gpu_common.h"

#define BLOCK_X 32
#define BLOCK_Y 8

__global__ void jacobi_step(const float *in, float *out, int n) {
  const int x = blockIdx.x * blockDim.x + threadIdx.x;
  const int y = blockIdx.y * blockDim.y + threadIdx.y;
  if (x <= 0 || y <= 0 || x >= n - 1 || y >= n - 1) return;

  const size_t idx = (size_t)y * n + x;
  out[idx] = 0.25f * (in[idx - 1] + in[idx + 1] +
                      in[idx - n] + in[idx + n]);
}

int main(int argc, char **argv) {
  const int n = (int)arg_or(argc, argv, 1, 4096);
  const long iterations = arg_or(argc, argv, 2, 500);
  print_header("stencil", n, iterations);

  const size_t elems = (size_t)n * n;
  const size_t bytes = elems * sizeof(float);
  float *h_grid = (float *)std::calloc(elems, sizeof(float));
  // Hot top edge drives the diffusion.
  for (int x = 0; x < n; ++x) h_grid[x] = 100.0f;

  float *d_a, *d_b;
  GPU_CHECK(gpuMalloc(&d_a, bytes));
  GPU_CHECK(gpuMalloc(&d_b, bytes));
  GPU_CHECK(gpuMemcpy(d_a, h_grid, bytes, gpuMemcpyHostToDevice));
  GPU_CHECK(gpuMemcpy(d_b, h_grid, bytes, gpuMemcpyHostToDevice));

  dim3 threads(BLOCK_X, BLOCK_Y);
  dim3 blocks((n + BLOCK_X - 1) / BLOCK_X, (n + BLOCK_Y - 1) / BLOCK_Y);
  for (long it = 0; it < iterations; ++it) {
    jacobi_step<<<blocks, threads>>>(d_a, d_b, n);
    float *tmp = d_a;   // ping-pong the buffers
    d_a = d_b;
    d_b = tmp;
  }
  GPU_CHECK_KERNEL();

  GPU_CHECK(gpuMemcpy(h_grid, d_a, bytes, gpuMemcpyDeviceToHost));
  // Heat must have spread from the top edge into the interior.
  const double probe = h_grid[(size_t)1 * n + n / 2];
  const bool ok = probe > 0.0 && probe <= 100.0;
  print_footer("stencil", probe, ok);

  GPU_CHECK(gpuFree(d_a));
  GPU_CHECK(gpuFree(d_b));
  std::free(h_grid);
  return ok ? 0 : 1;
}
