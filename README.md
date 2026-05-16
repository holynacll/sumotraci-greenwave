# SumoTraCI Greenwave

Framework de simulação para avaliar estratégias de preempção de veículos de
emergência (EV) sobre SUMO + TraCI. O codebase foi refatorado em torno de
**três estratégias** comparáveis no mesmo cenário:

- **`baseline`** — programa de sinalização padrão do SUMO, sem preempção. Piso absoluto.
- **`greenwave_legacy`** — green-wave original (pré-refactor), **congelado** como
  ponto de comparação (FSM 4-status, deadline puro, sem fila/anti-flicker/spillback,
  *safeguard* euclidiano de 0.8).
- **`greenwave`** — engine único refatorado. As melhorias são **compostas por
  configuração** (toggles `GW_*`), gerando 16 combinações sem explosão de classes
  (FSM 3-fase, prioridade plugável, anti-flicker, fila de pendentes, spillback BFS,
  visualização).
- **`mpc`** — Phase B, não implementada (`NotImplementedError`).

A documentação canônica das estratégias, da composição e do guia de ablação está
em [`docs/ALGORITHMS.md`](docs/ALGORITHMS.md).

Construído com arquitetura modular, Pydantic settings, e tooling moderno (`uv`, `typer`).

## Pré-requisitos

- **Python 3.11+**
- **[Eclipse SUMO](https://eclipse.dev/sumo/)** (>= 1.21.0)
- **[uv](https://github.com/astral-sh/uv)**

## Instalação

1.  **Dependências de runtime**:
    ```bash
    uv pip install -e .
    ```

2.  **Dependências de desenvolvimento (opcional)**:
    ```bash
    uv pip install -e .[dev]
    ```

## Uso

### 1. `SUMO_HOME`

```bash
export SUMO_HOME=/path/to/your/sumo
```

### 2. Rodar a simulação

```bash
uv run python -m sumotraci.main --nogui --simulation-end-time 900
```

**Opções comuns:**
- `--nogui`: roda sem GUI (headless).
- `--simulation-end-time FLOAT`: tempo de fim da simulação (s).
- `--time-block-accident FLOAT`: intervalo de bloqueio para criação de acidentes.
- `--vehicle-number INT`: total de veículos.
- `--algorithm STR`: estratégia (`baseline`, `greenwave_legacy`, `greenwave`, `mpc`).
- `--seed INT`: seed do RNG.
- `--help`: lista todas as opções.

A composição do `greenwave` (toggles `GW_*`) é definida via `.env` ou variáveis de
ambiente — não há flag CLI dedicada para cada toggle.

## Composição do `greenwave`

| Config | Tipo | Valores | Papel |
|---|---|---|---|
| `GW_PRIORITY` | *policy slot* | `deadline` \| `eta` | Cálculo do `priority_value` (sempre exatamente um). |
| `GW_ANTIFLICKER` | toggle | `true` \| `false` | Liga `MIN_EV_GREEN_HOLD` + `PREEMPT_DELTA_THRESHOLD`. |
| `GW_PENDING_QUEUE` | toggle | `true` \| `false` | Fila de alocações pendentes com hand-off. |
| `GW_SPILLBACK` | toggle | `true` \| `false` | Detector BFS + drenos em saídas saturadas. |

São **16 combinações** (2×2×2×2). Os defaults (`GW_PRIORITY=eta`, todos os
toggles `true`) reproduzem o antigo algoritmo `shield`.

Exemplos de `.env` para o estudo de ablação:

```bash
# EDF puro (sem nenhuma melhoria além da FSM 3-fase)
ALGORITHM=greenwave
GW_PRIORITY=deadline
GW_ANTIFLICKER=false
GW_PENDING_QUEUE=false
GW_SPILLBACK=false

# Greenwave completo (≡ antigo 'shield')
ALGORITHM=greenwave
```

A tabela completa de experimentos está em [`docs/ALGORITHMS.md`](docs/ALGORITHMS.md) §4.

## Estrutura do projeto

Código-fonte em `src/sumotraci/`:

- **`main.py`** — entry point CLI (Typer).
- **`core/`**
  - `simulation.py` — `SimulationEngine`.
  - `config.py` — `Settings` (Pydantic).
  - `sumo_interface.py` — wrapper tipado das chamadas TraCI.
- **`managers/`**
  - `accident_manager.py` — ciclo de vida de acidentes.
  - `emergency_manager.py` — dispatch e monitoramento de EVs.
  - `collision_manager.py` — colisões com **preservação seletiva do EV**
    (remove só civis; mantém EV vivo para a simulação continuar).
  - `traffic/` — pacote de controle de tráfego.
    - `manager.py` — `TrafficManager` (facade, delega à strategy).
    - `green_wave.py` — `GreenWaveManager`: FSM 3-fase + fila + anti-flicker + viz.
    - `edf.py` — `ArbitrationPolicy` Protocol + `EDFArbitration`.
    - `priority.py` — `PriorityPolicy` slot: `DeadlinePriority`, `ETAPriority`,
      `make_priority_policy()`.
    - `spillback.py` — `SpillbackDetector` (BFS-by-depth a partir do TLS raiz).
    - `strategies/`
      - `base.py` — `TrafficControlStrategy` ABC.
      - `baseline.py` — `NoOpStrategy`.
      - `legacy_greenwave.py` — `LegacyGreenWaveStrategy` (congelada).
      - `greenwave.py` — `GreenWaveStrategy` (composta via `GW_*`).
      - `__init__.py` — `make_strategy()`.
- **`domain/`** — schemas Pydantic e enums (`SeverityEnum`, `StatusEnum`).
- **`utils/`** — geração de cenário SUMO e pós-processamento XML→CSV.

## Estratégias

Selecionadas em runtime por `Settings.ALGORITHM` e despachadas por `make_strategy()`
em `managers/traffic/strategies/__init__.py`.

### `baseline` — `NoOpStrategy`

Sem intervenção em semáforos. Programas do SUMO rodam intactos. EVs não recebem
prioridade. Usado como piso absoluto de comparação.

### `greenwave_legacy` — `LegacyGreenWaveStrategy`

Versão original do green-wave (commit `664cef5`), **congelada**. FSM de 4 status
acoplado por flag (`INITIAL_TRANSITION` → `IN_PROGRESS` → `FINAL_TRANSITION` →
`RETURN_TO_PROGRAM_ORIGINAL`), prioridade por deadline cru, sem fila, sem
anti-flicker, sem spillback. Mantém o *safeguard* euclidiano
(`SAFE_GUARD_PROPORTION_FOR_COMPLETION_GWA = 0.8`). Não recebe plugins novos.

### `greenwave` — `GreenWaveStrategy`

Engine refatorado, composto via `GW_*`. A cada step a strategy:

1. Ordena EVs por `ev.deadline` (EDF).
2. Se `GW_SPILLBACK=true`: roda `SpillbackDetector.evaluate()` por EV, dispara
   `request_drain()` em sinais saturados, e monta `tls_to_skip`.
3. Para cada EV, para cada TLS dentro de `VEHICLE_DISTANCE_TO_TLS`:
   - Calcula `priority_value` via `PriorityPolicy.compute(ev, distance, current_speed)`.
   - Chama `GreenWaveManager.request(...)`.

O `GreenWaveManager` roda uma **FSM de 3 fases** por alocação:

| Fase | Ação na entrada | Condição de saída |
|---|---|---|
| `CLEARING` | Amarelo nos verdes opostos; preserva o estado da via do EV | Espera `TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT` (8 s) |
| `EV_GREEN` | Verde para a via do EV, vermelho no resto | `vehicle_get_next_tls` indica que o EV passou (event-driven) |
| `EXIT_YELLOW` | Amarelo nos verdes do EV | Espera 8 s, depois restaura ou faz hand-off |

Conflitos são resolvidos por **arbitragem EDF** (`can_preempt` com `delta` =
`PREEMPT_DELTA_THRESHOLD` se `GW_ANTIFLICKER` está on, senão 0). Quando uma
requisição perde a arbitragem para o holder atual, e `GW_PENDING_QUEUE=true`,
ela entra na **fila de pendentes** (priority-sorted). Ao final do holder, o
manager:

- promove a próxima pendente ainda relevante diretamente para `CLEARING`
  (**hand-off direto**, sem reabrir o programa original), ou
- restaura o programa original se a fila está vazia ou as pendentes saíram do range.

A fila é limpa ao fim de cada `tick()` e refeita pelas chamadas `request()` da
strategy no mesmo step (freshness guard).

Detalhes finos das diferenças `legacy → greenwave` estão na tabela de
[`docs/ALGORITHMS.md`](docs/ALGORITHMS.md) §3.

## Tratamento de colisões

Independente da estratégia escolhida, o `CollisionManager` global aplica
**preservação seletiva do EV**:

- SUMO roda com `--collision.action teleport`/`warn` (só registra o evento, não
  remove participantes).
- O `CollisionManager` remove **manualmente** apenas os participantes civis,
  garantindo que EVs continuem na simulação para que a `EmergencyManager` siga
  funcionando.
- Métricas exportadas em `tripinfo.csv` / `lanedata.csv`:
  - `COLLISIONS_INVOLVED` — civis removidos.
  - `EV_COLLISIONS` — eventos envolvendo um EV.
  - `COLLISION_STEPS` — número de steps com colisão registrada.

## Cenário de simulação

Próximo do default-puro do SUMO para focar em algoritmos de controle (não
engenharia de tráfego):

- Car-follow `Krauss` (livre de colisão por construção).
- Modelo lane-based (sem sublane / `--lateral-resolution`).
- `randomTrips.py --fringe-factor 10`.
- vTypes minimais; flags principais: `--time-to-teleport 60`,
  `--device.bluelight.reactiondist 40`.

## Desenvolvimento

### Lint

```bash
uv run ruff check src/sumotraci
```

### Configuração

Gerenciada via `src/sumotraci/core/config.py` (Pydantic `Settings`). Override
via variáveis de ambiente, `.env`, ou flags CLI. Principais settings do
`greenwave`:

| Setting | Default | Significado |
|---|---|---|
| `ALGORITHM` | `greenwave` | `baseline`, `greenwave_legacy`, `greenwave`, `mpc`. |
| `GW_PRIORITY` | `eta` | `deadline` ou `eta`. |
| `GW_ANTIFLICKER` | `True` | Liga `MIN_EV_GREEN_HOLD` + `PREEMPT_DELTA_THRESHOLD`. |
| `GW_PENDING_QUEUE` | `True` | Fila de pendentes com hand-off. |
| `GW_SPILLBACK` | `True` | Detector BFS + drenos. |
| `VEHICLE_DISTANCE_TO_TLS` | 400 | Distância máx. (m) EV→TLS para gerar `request()`. |
| `TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT` | 8.0 | Duração (s) das fases `CLEARING` e `EXIT_YELLOW`. |
| `MIN_EV_GREEN_HOLD` | 5.0 | Lock-out do `EV_GREEN` recém-iniciado (s). |
| `PREEMPT_DELTA_THRESHOLD` | 2.0 | Delta mínimo no `priority_value` para preemptar. |
| `SPILLBACK_OCCUPANCY_THRESHOLD` | 0.5 | Ocupação que dispara saturação. |
| `SPILLBACK_GRAPH_DEPTH` | 1 | Profundidade BFS do detector (1 = só TLS raiz). |
| `MIN_SPEED_FLOOR_FOR_ETA` | 5.0 | Piso de velocidade (m/s) no cálculo de ETA. |
| `HIGHLIGHT_ALLOCATIONS` | `True` | Visualização TraCI (faixa + marker no TLS). |

### Status do projeto

- Refatoração para **3 estratégias + composição por config** — **feito**.
- `LegacyGreenWaveStrategy` congelada como baseline de comparação — **feito**.
- `GreenWaveStrategy` (FSM 3-fase, anti-flicker, fila, spillback, viz) — **feito**.
- `CollisionManager` com preservação seletiva do EV — **feito**.
- `mpc` (Phase B) — **planejado**.

## Referências

- [`docs/ALGORITHMS.md`](docs/ALGORITHMS.md) — documento canônico: tabela de
  melhorias `legacy → greenwave`, guia de ablação, mapa de arquivos.
- [`docs/SPILLBACK_PLAN.md`](docs/SPILLBACK_PLAN.md) — design original do
  spillback (Phase A) e da Phase B.
- [`docs/MPC_PLAN.md`](docs/MPC_PLAN.md) — plano original do MPC (Phase B).
