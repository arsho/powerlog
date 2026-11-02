// vecadd_fp64 -- vector add followed by `intensity` FP64 FMAs per chain.
//
// Blackwell Ultra (GB300) has a much smaller FP64 rate than Hopper/B200, so
// the default intensity is lower than for FP32 to keep one pass short.
//
// Usage: ./bin/vecadd_fp64 [seconds=20] [intensity=64] [n=16777216]

#include "fma_vecadd.cuh"

int main(int argc, char **argv) {
  return fma_vecadd_main<double>(argc, argv, "vecadd_fp64", "FP64flop", 64,
                                 0.999, 0.001);
}
