// Shared helpers for the Powerlog example kernels.
//
// The same sources build for NVIDIA (nvcc) and AMD (hipcc). When compiled with
// hipcc, __HIP_PLATFORM_AMD__ is defined and the CUDA runtime names below are
// mapped onto their HIP equivalents.

#ifndef POWERLOG_GPU_COMMON_H
#define POWERLOG_GPU_COMMON_H

#include <cstdio>
#include <cstdlib>
#include <cmath>

#if defined(__HIP_PLATFORM_AMD__) || defined(USE_HIP)
#include <hip/hip_runtime.h>

#define gpuMalloc hipMalloc
#define gpuFree hipFree
#define gpuMemcpy hipMemcpy
#define gpuMemset hipMemset
#define gpuMemcpyHostToDevice hipMemcpyHostToDevice
#define gpuMemcpyDeviceToHost hipMemcpyDeviceToHost
#define gpuDeviceSynchronize hipDeviceSynchronize
#define gpuGetLastError hipGetLastError
#define gpuGetErrorString hipGetErrorString
#define gpuError_t hipError_t
#define gpuSuccess hipSuccess
#define gpuGetDeviceProperties hipGetDeviceProperties
#define gpuDeviceProp hipDeviceProp_t
#else
#include <cuda_runtime.h>

#define gpuMalloc cudaMalloc
#define gpuFree cudaFree
#define gpuMemcpy cudaMemcpy
#define gpuMemset cudaMemset
#define gpuMemcpyHostToDevice cudaMemcpyHostToDevice
#define gpuMemcpyDeviceToHost cudaMemcpyDeviceToHost
#define gpuDeviceSynchronize cudaDeviceSynchronize
#define gpuGetLastError cudaGetLastError
#define gpuGetErrorString cudaGetErrorString
#define gpuError_t cudaError_t
#define gpuSuccess cudaSuccess
#define gpuGetDeviceProperties cudaGetDeviceProperties
#define gpuDeviceProp cudaDeviceProp
#endif

// Abort with a readable message if a runtime call fails.
#define GPU_CHECK(call)                                                        \
  do {                                                                         \
    gpuError_t _err = (call);                                                  \
    if (_err != gpuSuccess) {                                                  \
      std::fprintf(stderr, "%s:%d: GPU error: %s\n", __FILE__, __LINE__,       \
                   gpuGetErrorString(_err));                                   \
      std::exit(EXIT_FAILURE);                                                 \
    }                                                                          \
  } while (0)

// Check that the most recent kernel launch succeeded, then synchronize.
#define GPU_CHECK_KERNEL()                                                     \
  do {                                                                         \
    GPU_CHECK(gpuGetLastError());                                              \
    GPU_CHECK(gpuDeviceSynchronize());                                         \
  } while (0)

// Parse argv[index] as a long, falling back to fallback_value.
inline long arg_or(int argc, char **argv, int index, long fallback_value) {
  if (index >= argc) return fallback_value;
  char *end = nullptr;
  long value = std::strtol(argv[index], &end, 10);
  return (end == argv[index] || value <= 0) ? fallback_value : value;
}

// Print the banner shared by every example so runs are easy to identify.
inline void print_header(const char *name, long size, long iterations) {
  std::printf("[%s] size=%ld iterations=%ld\n", name, size, iterations);
}

// Print the result footer: checksum lets you confirm the kernel really ran.
inline void print_footer(const char *name, double checksum, bool ok) {
  std::printf("[%s] checksum=%.6f verification=%s\n", name, checksum,
              ok ? "PASS" : "FAIL");
}

#endif  // POWERLOG_GPU_COMMON_H
