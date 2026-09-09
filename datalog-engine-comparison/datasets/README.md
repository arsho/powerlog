# Datasets

Nothing needs to be downloaded. The graphs ship inside the engine repositories,
already converted to each engine's input format. `datasets.csv` maps every
dataset to its file in each repository.

| Engine | Repository | Input format | Location |
| ------ | ---------- | ------------ | -------- |
| MNMGDatalog, INLJoin | `harp-lab/MNMGDatalog` | packed binary edge list | `data/data_<edges>.bin` |
| cuDF | `harp-lab/MNMGDatalog` | plain-text edge list | `data/data_<edges>.txt` |
| GPULog | `harp-lab/gdlog` | Souffle facts | `data/<name>/edge.facts` |
| BJoin | `harp-lab/batch_joins` | plain-text edge list | `data/<name>.txt` |

So cloning MNMGDatalog and gdlog gives you every input those four engines need.

## BJoin inputs

`batch_joins` does not ship its `data/` directory. Its inputs are plain-text
whitespace-separated edge lists, the same content as the MNMGDatalog `.txt`
files, so they can be copied across:

```bash
cp ~/MNMGDatalog/data/data_163734.txt ~/batch_joins/data/fe_body.txt
cp ~/MNMGDatalog/data/data_223001.txt ~/batch_joins/data/sf.txt
cp ~/MNMGDatalog/data/data_49152.txt  ~/batch_joins/data/fe_sphere.txt
cp ~/MNMGDatalog/data/data_51971.txt  ~/batch_joins/data/ca_hepth.txt
cp ~/MNMGDatalog/data/data_214078.txt ~/batch_joins/data/loc-brightkite.txt
```

`usroads` and `vsp` have no `.txt` in MNMGDatalog; derive them from the GPULog
facts files, which are the same edge lists:

```bash
cp ~/gdlog/data/usroad/edge.facts    ~/batch_joins/data/usroads.txt
cp ~/gdlog/data/vsp_finan/edge.facts ~/batch_joins/data/vsp.txt
```

## Coverage

cuDF is only run where it produced valid, non-OOM results: TC on `fe_body` and
`sf`, and SG on `ca_hepth`, `fe_sphere` and `loc-brightkite`. That is why
`usroads` and `vsp` have no cuDF entry in `datasets.csv` and appear as OOM in the
results tables.

## Provenance

The graphs originate from the
[SuiteSparse Matrix Collection](https://sparse.tamu.edu) and
[SNAP](https://snap.stanford.edu/data); per-graph URLs are in `datasets.csv`.
These are listed for attribution only -- use the copies in the engine
repositories, which are already in the required formats.
