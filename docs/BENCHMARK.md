# Benchmark com as 10 seeds

O script `sumotraci.scripts.eval_multi_seed` roda cada algoritmo nas 10 seeds de
avaliação (`Settings.SEEDS`) e junta os resultados num CSV por configuração.
Medido em 29/10/2026: por seed, ~11 s no `baseline`, ~15 s no `greenwave_legacy` e
~20 s no `greenwave`; as 30 rodadas levam cerca de 8 minutos.

## 1. Preparar o terminal

```bash
cd ~/workspace/sumotraci-greenwave
git switch main && git pull
uv sync
export SUMO_HOME=$(uv run python -c "import sumo; print(sumo.SUMO_HOME)")
ls .env        # "No such file" = valem os defaults do config.py
mkdir -p logs
```

O `SUMO_HOME` vale só para o terminal aberto; num terminal novo, exporte de novo.

## 2. Teste rápido (uma seed, menos de 1 minuto)

```bash
uv run python -u -m sumotraci.scripts.eval_multi_seed \
    --algorithm baseline greenwave_legacy greenwave --seeds 428956419
```

Deve terminar com três linhas `[benchmark] <algoritmo> seed=428956419 saveds=… unsaveds=…`
e sem nenhum `Error parsing XML` na saída.

## 3. Rodar o benchmark

```bash
caffeinate -i uv run python -u -m sumotraci.scripts.eval_multi_seed \
    --algorithm baseline greenwave_legacy greenwave > logs/benchmark.log 2>&1
```

- `caffeinate -i` impede o Mac de dormir durante as rodadas.
- `-u` faz o progresso chegar ao log na hora.
- Para acompanhar, em outro terminal:
  `tail -f logs/benchmark.log | grep --line-buffered "\[benchmark\]"`
- Não rode dois benchmarks ao mesmo tempo na mesma pasta: toda rodada reescreve
  `data/road.net.xml`, `data/route.rou.xml` e `data/config.sumocfg`.

## 4. Conferir

```bash
grep -c "saveds=" logs/benchmark.log         # 30 (10 seeds x 3 algoritmos)
grep -cE "FAILED|Error parsing" logs/benchmark.log   # 0
```

Se uma seed falhar, o script termina com `failed runs: <label>/<seed>` e status
diferente de zero; o CSV juntado traz só as seeds que deram certo. O traceback da
falha está no log.

Resumo rápido por algoritmo:

```bash
uv run python - <<'EOF'
import pandas as pd

for label in ["baseline", "greenwave_legacy", "greenwave"]:
    df = pd.read_csv(f"data/tripinfo_{label}_merged.csv")
    ev = df[df.vType == "emergency_emergency"]
    per_seed = df.groupby("seed")[["SAVEDS", "UNSAVEDS"]].first()
    print(
        f"{label:18s} seeds={per_seed.shape[0]:2d}  "
        f"tempo médio do VE={ev.duration.mean():6.1f} s  "
        f"salvos={per_seed.SAVEDS.sum()}/{(per_seed.SAVEDS + per_seed.UNSAVEDS).sum()}"
    )
EOF
```

O número de acidentes muda entre algoritmos na mesma seed, porque depende do
tráfego. Compare os salvos como proporção, não em valor absoluto.

## 5. Variantes do `greenwave`

O `greenwave` usa a composição do `config.py`; hoje ela tem `GW_PRIORITY=eta` e
`GW_EV_PREEMPTION`, `GW_ANTIFLICKER`, `GW_SPILLBACK` e `GW_FAST_HANDOFF` ligados.
Para outra composição, passe as variáveis na frente do comando e dê um `--label`
próprio, senão ela sobrescreve os arquivos do `greenwave` padrão:

```bash
GW_EV_PREEMPTION=false caffeinate -i uv run python -u -m sumotraci.scripts.eval_multi_seed \
    --algorithm greenwave --label greenwave_sem_preempcao > logs/benchmark_sem_preempcao.log 2>&1
```

| Variável | Valores | Observação |
|---|---|---|
| `GW_PRIORITY` | `eta`, `deadline` | Sempre exatamente uma |
| `GW_EV_PREEMPTION` | `true`, `false` | Preempção entre VEs, só no verde |
| `GW_ANTIFLICKER` | `true`, `false` | Só tem efeito com `GW_EV_PREEMPTION=true` |
| `GW_SPILLBACK` | `true`, `false` | Detector de spillback e drenos |
| `GW_FAST_HANDOFF` | `true`, `false` | Sucessor da fila entra direto no verde |

As 12 combinações distintas da ablação estão em [ALGORITHMS.md](ALGORITHMS.md).

## 6. O que sai

| Arquivo | Conteúdo |
|---|---|
| `data/tripinfo_<label>_<seed>.csv` | Uma linha por veículo de uma rodada; emissões só no VE |
| `data/lanedata_<label>_<seed>.csv` | Uma linha por faixa de uma rodada |
| `data/tripinfo_<label>_merged.csv` | As seeds juntas, com as colunas `seed`, `ALGORITHM` e `LABEL` |
| `data/lanedata_<label>_merged.csv` | Idem, por faixa |

`data/` não vai para o git, e rodar de novo o mesmo label sobrescreve os arquivos.
Para guardar uma rodada:

```bash
mkdir -p data/benchmark-$(date +%F) && cp data/*_merged.csv data/benchmark-$(date +%F)/
```

## 7. Depois: a análise

Os notebooks em `src/sumotraci/notebooks/` são de 2024 e leem outros nomes de
arquivo. A análise para os slides (média por seed, IC de 95% com t de Student para
n = 10, comparação pareada por seed) ainda precisa de um notebook sobre os
`*_merged.csv`.
