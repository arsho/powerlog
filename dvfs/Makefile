# DVFS / power-control micro-benchmarks.
#
#   make                    # ARCH=native: build for the GPU in this node
#   make ARCH=sm_103        # GB300 / B300 (Blackwell Ultra), e.g. on a login node
#   make ARCH=sm_100        # GB200 / B200
#   make clean
#
# Needs nvcc (CUDA 12.9+ for sm_103) and libnvidia-ml (ships with the driver).
# If the linker cannot find libnvidia-ml, point NVML_LIB at the CUDA stubs:
#   make NVML_LIB=$CUDA_HOME/targets/sbsa-linux/lib/stubs

NVCC     ?= nvcc
ARCH     ?= native
NVML_LIB ?=
NVCCFLAGS ?= -O3 -std=c++17 -lineinfo
LDLIBS   := $(if $(NVML_LIB),-L$(NVML_LIB)) -lnvidia-ml -lpthread

BINDIR := bin
SRC    := $(wildcard *.cu)
BIN    := $(patsubst %.cu,$(BINDIR)/%,$(SRC))

.PHONY: all clean sass

all: $(BIN)

$(BINDIR)/%: %.cu common.h fma_vecadd.cuh | $(BINDIR)
	$(NVCC) $(NVCCFLAGS) -arch=$(ARCH) -o $@ $< $(LDLIBS)

$(BINDIR):
	mkdir -p $(BINDIR)

# Confirm the inner loops compiled to FFMA / DFMA / IMAD / HFMA2.
sass: all
	@for b in $(BIN); do \
	  echo "== $$b"; \
	  cuobjdump -sass $$b | grep -oE '\b(FFMA|DFMA|IMAD|HFMA2)\b' | sort | uniq -c; \
	done

clean:
	rm -rf $(BINDIR)
