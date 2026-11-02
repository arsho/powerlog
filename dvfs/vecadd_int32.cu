// vecadd_int32 -- vector add followed by `intensity` INT32 multiply-adds
// (an LCG step, compiled to IMAD) per chain. Exercises the integer pipe, whose
// power draw per op differs from the FP32 pipe at the same clock.
//
// Usage: ./bin/vecadd_int32 [seconds=20] [intensity=512] [n=16777216]

#include "fma_vecadd.cuh"

int main(int argc, char **argv) {
  return fma_vecadd_main<uint32_t>(argc, argv, "vecadd_int32", "INT32op", 512,
                                   1664525u, 1013904223u);
}
