// matmul_sycl -- tiled dense matrix multiply in SYCL.
//
// The SYCL counterpart of apps/cuda/matmul.cu, using local memory tiles and an
// nd_range so the blocking strategy matches the CUDA/HIP version.
//
// Usage: ./matmul_sycl [matrix_dim] [iterations]

#include <sycl/sycl.hpp>

#include <cmath>
#include <cstdio>
#include <cstdlib>

constexpr int kTile = 16;

static long arg_or(int argc, char **argv, int index, long fallback) {
  if (index >= argc) return fallback;
  char *end = nullptr;
  long value = std::strtol(argv[index], &end, 10);
  return (end == argv[index] || value <= 0) ? fallback : value;
}

int main(int argc, char **argv) {
  int n = (int)arg_or(argc, argv, 1, 2048);
  const long iterations = arg_or(argc, argv, 2, 50);
  // Round up to a whole number of tiles to keep the nd_range valid.
  n = ((n + kTile - 1) / kTile) * kTile;

  sycl::queue q{sycl::default_selector_v};
  std::printf("[matmul_sycl] device=%s\n",
              q.get_device().get_info<sycl::info::device::name>().c_str());
  std::printf("[matmul_sycl] size=%d iterations=%ld\n", n, iterations);

  const size_t elems = (size_t)n * n;
  float *A = sycl::malloc_device<float>(elems, q);
  float *B = sycl::malloc_device<float>(elems, q);
  float *C = sycl::malloc_device<float>(elems, q);
  q.fill(A, 1.0f, elems).wait();
  q.fill(B, 1.0f, elems).wait();

  const sycl::range<2> global(n, n);
  const sycl::range<2> local(kTile, kTile);

  for (long it = 0; it < iterations; ++it) {
    q.submit([&](sycl::handler &h) {
      sycl::local_accessor<float, 2> tile_a({kTile, kTile}, h);
      sycl::local_accessor<float, 2> tile_b({kTile, kTile}, h);

      h.parallel_for(sycl::nd_range<2>(global, local), [=](sycl::nd_item<2> item) {
        const int row = item.get_global_id(0);
        const int col = item.get_global_id(1);
        const int ty = item.get_local_id(0);
        const int tx = item.get_local_id(1);

        float acc = 0.0f;
        for (int t = 0; t < n / kTile; ++t) {
          tile_a[ty][tx] = A[(size_t)row * n + t * kTile + tx];
          tile_b[ty][tx] = B[(size_t)(t * kTile + ty) * n + col];
          item.barrier(sycl::access::fence_space::local_space);

          for (int k = 0; k < kTile; ++k) {
            acc += tile_a[ty][k] * tile_b[k][tx];
          }
          item.barrier(sycl::access::fence_space::local_space);
        }
        C[(size_t)row * n + col] = acc;
      });
    });
  }
  q.wait();

  float first = 0.0f;
  q.memcpy(&first, C, sizeof(float)).wait();

  const bool ok = std::fabs(first - (float)n) < 1e-2f * n;
  const double gflop = 2.0 * n * n * (double)n * iterations / 1e9;
  std::printf("[matmul_sycl] total work=%.2f GFLOP\n", gflop);
  std::printf("[matmul_sycl] checksum=%.6f verification=%s\n", first,
              ok ? "PASS" : "FAIL");

  sycl::free(A, q);
  sycl::free(B, q);
  sycl::free(C, q);
  return ok ? 0 : 1;
}
