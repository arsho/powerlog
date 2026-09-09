// matmul -- tiled dense matrix multiply using shared memory (compute bound).
//
// The classic shared-memory blocked SGEMM. Compared with vecadd this has a much
// higher arithmetic intensity, so it keeps the GPU near its power ceiling.
//
// Usage: ./matmul [matrix_dim] [iterations]

#include "gpu_common.h"

#define TILE 16

__global__ void matmul_tiled(const float *A, const float *B, float *C, int n) {
  __shared__ float tile_a[TILE][TILE];
  __shared__ float tile_b[TILE][TILE];

  const int row = blockIdx.y * TILE + threadIdx.y;
  const int col = blockIdx.x * TILE + threadIdx.x;
  float acc = 0.0f;

  for (int t = 0; t < (n + TILE - 1) / TILE; ++t) {
    const int a_col = t * TILE + threadIdx.x;
    const int b_row = t * TILE + threadIdx.y;
    tile_a[threadIdx.y][threadIdx.x] =
        (row < n && a_col < n) ? A[(size_t)row * n + a_col] : 0.0f;
    tile_b[threadIdx.y][threadIdx.x] =
        (b_row < n && col < n) ? B[(size_t)b_row * n + col] : 0.0f;
    __syncthreads();

    for (int k = 0; k < TILE; ++k) {
      acc += tile_a[threadIdx.y][k] * tile_b[k][threadIdx.x];
    }
    __syncthreads();
  }

  if (row < n && col < n) C[(size_t)row * n + col] = acc;
}

int main(int argc, char **argv) {
  const int n = (int)arg_or(argc, argv, 1, 2048);
  const long iterations = arg_or(argc, argv, 2, 50);
  print_header("matmul", n, iterations);

  const size_t elems = (size_t)n * n;
  const size_t bytes = elems * sizeof(float);
  float *h_a = (float *)std::malloc(bytes);
  float *h_c = (float *)std::malloc(bytes);
  for (size_t i = 0; i < elems; ++i) h_a[i] = 1.0f;

  float *d_a, *d_b, *d_c;
  GPU_CHECK(gpuMalloc(&d_a, bytes));
  GPU_CHECK(gpuMalloc(&d_b, bytes));
  GPU_CHECK(gpuMalloc(&d_c, bytes));
  GPU_CHECK(gpuMemcpy(d_a, h_a, bytes, gpuMemcpyHostToDevice));
  GPU_CHECK(gpuMemcpy(d_b, h_a, bytes, gpuMemcpyHostToDevice));

  dim3 threads(TILE, TILE);
  dim3 blocks((n + TILE - 1) / TILE, (n + TILE - 1) / TILE);
  for (long it = 0; it < iterations; ++it) {
    matmul_tiled<<<blocks, threads>>>(d_a, d_b, d_c, n);
  }
  GPU_CHECK_KERNEL();

  GPU_CHECK(gpuMemcpy(h_c, d_c, bytes, gpuMemcpyDeviceToHost));
  // Every element of A and B is 1.0, so each output element must equal n.
  const bool ok = std::fabs(h_c[0] - (float)n) < 1e-2f * n;
  const double gflop = 2.0 * n * n * (double)n * iterations / 1e9;
  std::printf("[matmul] total work=%.2f GFLOP\n", gflop);
  print_footer("matmul", h_c[0], ok);

  GPU_CHECK(gpuFree(d_a));
  GPU_CHECK(gpuFree(d_b));
  GPU_CHECK(gpuFree(d_c));
  std::free(h_a);
  std::free(h_c);
  return ok ? 0 : 1;
}
