// nbody -- direct O(N^2) gravitational N-body step (compute bound, FMA heavy).
//
// Each body is attracted to every other body. Tiling the body list through
// shared memory makes this one of the highest sustained-power kernels in the
// set, which makes it a good stress case for energy measurement.
//
// Usage: ./nbody [n_bodies] [iterations]

#include "gpu_common.h"

#define BLOCK 256
#define SOFTENING 1e-9f

struct Body {
  float x, y, z;
  float vx, vy, vz;
};

__global__ void body_force(Body *bodies, float dt, int n) {
  __shared__ float3 shared_pos[BLOCK];
  const int i = blockIdx.x * blockDim.x + threadIdx.x;

  float fx = 0.0f, fy = 0.0f, fz = 0.0f;
  const float xi = (i < n) ? bodies[i].x : 0.0f;
  const float yi = (i < n) ? bodies[i].y : 0.0f;
  const float zi = (i < n) ? bodies[i].z : 0.0f;

  for (int tile = 0; tile < gridDim.x; ++tile) {
    const int j = tile * blockDim.x + threadIdx.x;
    if (j < n) {
      shared_pos[threadIdx.x] =
          make_float3(bodies[j].x, bodies[j].y, bodies[j].z);
    } else {
      shared_pos[threadIdx.x] = make_float3(0.0f, 0.0f, 0.0f);
    }
    __syncthreads();

    for (int k = 0; k < BLOCK; ++k) {
      const float dx = shared_pos[k].x - xi;
      const float dy = shared_pos[k].y - yi;
      const float dz = shared_pos[k].z - zi;
      const float dist_sq = dx * dx + dy * dy + dz * dz + SOFTENING;
      const float inv_dist = rsqrtf(dist_sq);
      const float inv_dist3 = inv_dist * inv_dist * inv_dist;
      fx += dx * inv_dist3;
      fy += dy * inv_dist3;
      fz += dz * inv_dist3;
    }
    __syncthreads();
  }

  if (i < n) {
    bodies[i].vx += dt * fx;
    bodies[i].vy += dt * fy;
    bodies[i].vz += dt * fz;
  }
}

__global__ void integrate(Body *bodies, float dt, int n) {
  const int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i >= n) return;
  bodies[i].x += bodies[i].vx * dt;
  bodies[i].y += bodies[i].vy * dt;
  bodies[i].z += bodies[i].vz * dt;
}

int main(int argc, char **argv) {
  const int n = (int)arg_or(argc, argv, 1, 65536);
  const long iterations = arg_or(argc, argv, 2, 100);
  print_header("nbody", n, iterations);

  const size_t bytes = (size_t)n * sizeof(Body);
  Body *h_bodies = (Body *)std::malloc(bytes);
  // Deterministic pseudo-random initial state (no <random> dependency).
  unsigned seed = 1234u;
  for (int i = 0; i < n; ++i) {
    seed = seed * 1103515245u + 12345u;
    const float r = (float)((seed >> 16) & 0x7fff) / 32767.0f * 2.0f - 1.0f;
    h_bodies[i] = Body{r, -r, r * 0.5f, 0.0f, 0.0f, 0.0f};
  }

  Body *d_bodies;
  GPU_CHECK(gpuMalloc(&d_bodies, bytes));
  GPU_CHECK(gpuMemcpy(d_bodies, h_bodies, bytes, gpuMemcpyHostToDevice));

  const int blocks = (n + BLOCK - 1) / BLOCK;
  const float dt = 0.01f;
  for (long it = 0; it < iterations; ++it) {
    body_force<<<blocks, BLOCK>>>(d_bodies, dt, n);
    integrate<<<blocks, BLOCK>>>(d_bodies, dt, n);
  }
  GPU_CHECK_KERNEL();

  GPU_CHECK(gpuMemcpy(h_bodies, d_bodies, bytes, gpuMemcpyDeviceToHost));
  const bool ok = std::isfinite(h_bodies[0].x) && std::isfinite(h_bodies[0].vx);
  const double ginter = (double)n * n * iterations / 1e9;
  std::printf("[nbody] total work=%.2f G-interactions\n", ginter);
  print_footer("nbody", h_bodies[0].x, ok);

  GPU_CHECK(gpuFree(d_bodies));
  std::free(h_bodies);
  return ok ? 0 : 1;
}
