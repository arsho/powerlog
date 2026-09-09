// gemm -- vendor-library SGEMM (cuBLAS on NVIDIA, hipBLAS on AMD).
//
// The tuned counterpart to matmul.cu. Comparing the two under Powerlog shows how
// much energy a hand-written kernel gives up against the vendor library.
//
// Usage: ./gemm [matrix_dim] [iterations]

#include "gpu_common.h"

#if defined(__HIP_PLATFORM_AMD__) || defined(USE_HIP)
#include <hipblas/hipblas.h>
#define blasHandle_t hipblasHandle_t
#define blasCreate hipblasCreate
#define blasDestroy hipblasDestroy
#define blasSgemm hipblasSgemm
#define BLAS_OP_N HIPBLAS_OP_N
#define BLAS_STATUS_SUCCESS HIPBLAS_STATUS_SUCCESS
#else
#include <cublas_v2.h>
#define blasHandle_t cublasHandle_t
#define blasCreate cublasCreate
#define blasDestroy cublasDestroy
#define blasSgemm cublasSgemm
#define BLAS_OP_N CUBLAS_OP_N
#define BLAS_STATUS_SUCCESS CUBLAS_STATUS_SUCCESS
#endif

#define BLAS_CHECK(call)                                                       \
  do {                                                                         \
    if ((call) != BLAS_STATUS_SUCCESS) {                                       \
      std::fprintf(stderr, "%s:%d: BLAS call failed\n", __FILE__, __LINE__);   \
      std::exit(EXIT_FAILURE);                                                 \
    }                                                                          \
  } while (0)

int main(int argc, char **argv) {
  const int n = (int)arg_or(argc, argv, 1, 4096);
  const long iterations = arg_or(argc, argv, 2, 50);
  print_header("gemm", n, iterations);

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

  blasHandle_t handle;
  BLAS_CHECK(blasCreate(&handle));
  const float alpha = 1.0f, beta = 0.0f;

  for (long it = 0; it < iterations; ++it) {
    // C = alpha * A * B + beta * C, column-major as BLAS expects.
    BLAS_CHECK(blasSgemm(handle, BLAS_OP_N, BLAS_OP_N, n, n, n, &alpha,
                         d_a, n, d_b, n, &beta, d_c, n));
  }
  GPU_CHECK(gpuDeviceSynchronize());

  GPU_CHECK(gpuMemcpy(h_c, d_c, bytes, gpuMemcpyDeviceToHost));
  const bool ok = std::fabs(h_c[0] - (float)n) < 1e-2f * n;
  const double gflop = 2.0 * n * n * (double)n * iterations / 1e9;
  std::printf("[gemm] total work=%.2f GFLOP\n", gflop);
  print_footer("gemm", h_c[0], ok);

  BLAS_CHECK(blasDestroy(handle));
  GPU_CHECK(gpuFree(d_a));
  GPU_CHECK(gpuFree(d_b));
  GPU_CHECK(gpuFree(d_c));
  std::free(h_a);
  std::free(h_c);
  return ok ? 0 : 1;
}
