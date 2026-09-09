// vecadd_sycl -- element-wise vector addition in SYCL.
//
// The SYCL counterpart of apps/cuda/vecadd.cu. A single binary runs on Intel,
// NVIDIA and AMD GPUs, so it is handy for cross-vendor energy comparisons with
// `powerlog --gpu-backend {intel,nvidia,amd}`.
//
// Usage: ./vecadd_sycl [n_elements] [iterations]

#include <sycl/sycl.hpp>

#include <cmath>
#include <cstdio>
#include <cstdlib>

static long arg_or(int argc, char **argv, int index, long fallback) {
  if (index >= argc) return fallback;
  char *end = nullptr;
  long value = std::strtol(argv[index], &end, 10);
  return (end == argv[index] || value <= 0) ? fallback : value;
}

int main(int argc, char **argv) {
  const long n = arg_or(argc, argv, 1, 1L << 26);
  const long iterations = arg_or(argc, argv, 2, 200);

  sycl::queue q{sycl::default_selector_v};
  std::printf("[vecadd_sycl] device=%s\n",
              q.get_device().get_info<sycl::info::device::name>().c_str());
  std::printf("[vecadd_sycl] size=%ld iterations=%ld\n", n, iterations);

  float *a = sycl::malloc_device<float>(n, q);
  float *b = sycl::malloc_device<float>(n, q);
  float *c = sycl::malloc_device<float>(n, q);

  q.fill(a, 1.0f, n).wait();
  q.fill(b, 1.0f, n).wait();

  for (long it = 0; it < iterations; ++it) {
    q.parallel_for(sycl::range<1>(n), [=](sycl::id<1> i) {
      c[i] = a[i] + b[i];
    });
  }
  q.wait();

  float first = 0.0f;
  q.memcpy(&first, c, sizeof(float)).wait();

  const bool ok = std::fabs(first - 2.0f) < 1e-5f;
  std::printf("[vecadd_sycl] checksum=%.6f verification=%s\n", first,
              ok ? "PASS" : "FAIL");

  sycl::free(a, q);
  sycl::free(b, q);
  sycl::free(c, q);
  return ok ? 0 : 1;
}
