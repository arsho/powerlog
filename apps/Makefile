# Build the Powerlog example GPU applications.
#
#   make                 # build the CUDA/HIP apps with the detected toolchain
#   make BACKEND=cuda    # force NVIDIA (nvcc)
#   make BACKEND=hip     # force AMD (hipcc)
#   make sycl            # build the SYCL apps (icpx or clang++)
#   make all             # CUDA/HIP apps + SYCL apps
#   make run             # build, then profile every app with powerlog
#   make clean

BINDIR   := bin
CUDA_SRC := $(wildcard cuda/*.cu)
SYCL_SRC := $(wildcard sycl/*.cpp)

# ---- backend auto-detection ------------------------------------------------
ifeq ($(origin BACKEND), undefined)
  ifneq ($(shell command -v nvcc 2>/dev/null),)
    BACKEND := cuda
  else ifneq ($(shell command -v hipcc 2>/dev/null),)
    BACKEND := hip
  else
    BACKEND := none
  endif
endif

# gemm needs the vendor BLAS; every other app is runtime-only.
ifeq ($(BACKEND),cuda)
  GPUCC     := nvcc
  GPUFLAGS  := -O3 -std=c++17
  BLAS_LIBS := -lcublas
else ifeq ($(BACKEND),hip)
  GPUCC     := hipcc
  GPUFLAGS  := -O3 -std=c++17 -DUSE_HIP
  BLAS_LIBS := -lhipblas
endif

# ---- SYCL compiler ---------------------------------------------------------
ifneq ($(shell command -v icpx 2>/dev/null),)
  SYCLCC    := icpx
  SYCLFLAGS := -O3 -std=c++17 -fsycl
else
  SYCLCC    := clang++
  SYCLFLAGS := -O3 -std=c++17 -fsycl
endif

CUDA_BIN := $(patsubst cuda/%.cu,$(BINDIR)/%,$(CUDA_SRC))
SYCL_BIN := $(patsubst sycl/%.cpp,$(BINDIR)/%,$(SYCL_SRC))

.PHONY: gpu sycl all run clean help

gpu: $(CUDA_BIN)

sycl: $(SYCL_BIN)

all: gpu sycl

ifeq ($(BACKEND),none)
$(CUDA_BIN):
	@echo "error: no GPU compiler found (need nvcc or hipcc)."
	@echo "       install CUDA or ROCm, or run 'make sycl' instead."
	@false
else
# gemm links against cuBLAS/hipBLAS.
$(BINDIR)/gemm: cuda/gemm.cu cuda/gpu_common.h | $(BINDIR)
	$(GPUCC) $(GPUFLAGS) -o $@ $< $(BLAS_LIBS)

$(BINDIR)/%: cuda/%.cu cuda/gpu_common.h | $(BINDIR)
	$(GPUCC) $(GPUFLAGS) -o $@ $<
endif

$(BINDIR)/%: sycl/%.cpp | $(BINDIR)
	$(SYCLCC) $(SYCLFLAGS) -o $@ $<

$(BINDIR):
	mkdir -p $(BINDIR)

# Profile every built binary and write one CSV per app into results/.
run: gpu
	@mkdir -p results
	@for app in $(notdir $(CUDA_BIN)); do \
	  echo "=== $$app ==="; \
	  powerlog --output results/$$app.csv ./$(BINDIR)/$$app || exit 1; \
	done

clean:
	rm -rf $(BINDIR) results

help:
	@echo "Powerlog example applications"
	@echo "  BACKEND=$(BACKEND)  GPUCC=$(GPUCC)  SYCLCC=$(SYCLCC)"
	@echo ""
	@echo "targets: gpu (default), sycl, all, run, clean"
