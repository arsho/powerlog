// vecadd_fp32 -- vector add followed by `intensity` FP32 FMAs per chain.
//
// Compute bound (FFMA) at the default intensity; drop intensity to 1-4 to make
// it bandwidth bound. Throughput should track the SM clock almost linearly.
//
// Usage: ./bin/vecadd_fp32 [seconds=20] [intensity=512] [n=16777216]

#include "fma_vecadd.cuh"

int main(int argc, char **argv) {
  return fma_vecadd_main<float>(argc, argv, "vecadd_fp32", "FP32flop", 512,
                                0.999f, 0.001f);
}
