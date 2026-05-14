# Algoritmos de controle e ablação

Este documento descreve os algoritmos de controle de tráfego do projeto, as
melhorias incrementais introduzidas no *green-wave*, e como executar o estudo de
ablação que isola a contribuição de cada melhoria.

## 1. Três estratégias

Toda strategy implementa `TrafficControlStrategy` e é selecionada em tempo de
execução via `Settings.ALGORITHM`.

| `ALGORITHM` | Strategy | Papel |
|---|---|---|
| `baseline` | `NoOpStrategy` | Controle de tráfego padrão do SUMO, sem qualquer preempção para EVs. Piso absoluto. |
| `greenwave_legacy` | `LegacyGreenWaveStrategy` | Versão original do green-wave (commit `664cef5`), pré-refactor. **Congelada** — não recebe plugins, mantida só para comparação. |
| `greenwave` | `GreenWaveStrategy` | Engine único refatorado. As melhorias são **compostas por configuração** (toggles `GW_*`). |
| `mpc` | — | Phase B, não implementado (ver `docs/MPC_PLAN.md`). |

A explosão de classes anterior (`fsm_greenwave`, `edf_greenwave`, `proposto`,
`shield`) foi colapsada em `greenwave` + configuração.

## 2. Composição do `greenwave`

O `greenwave` é parametrizado por quatro chaves no `Settings` (variáveis de
ambiente ou `.env`):

| Config | Tipo | Valores | Papel |
|---|---|---|---|
| `GW_PRIORITY` | *policy slot* | `deadline` \| `eta` | Como calcular o valor de prioridade de um pedido de EV num TLS. Sempre exatamente um. |
| `GW_ANTIFLICKER` | toggle | `true` \| `false` | Liga/desliga `MIN_EV_GREEN_HOLD` + `PREEMPT_DELTA_THRESHOLD`. Quando off, os dois são zerados. |
| `GW_PENDING_QUEUE` | toggle | `true` \| `false` | Liga/desliga a fila de alocações pendentes com hand-off. Quando off, o perdedor da arbitragem é descartado. |
| `GW_SPILLBACK` | toggle | `true` \| `false` | Liga/desliga o detector de spillback BFS + mecanismo de drenos. |

São **2×2×2×2 = 16 combinações**, todas válidas e construíveis.

### Policy slot — `GW_PRIORITY`

| Valor | Métrica | Comportamento |
|---|---|---|
| `deadline` | `ev.deadline` cru (`SEVERITY_GOLDEN_TIME[severity]`) | EDF puro. Um EV mais crítico mas distante supera um menos crítico mas próximo. |
| `eta` | `distance / max(speed, MIN_SPEED_FLOOR_FOR_ETA) + SEVERITY_ETA_PENALTY[severity]` | Proximidade domina; severidade é desempate fino. |

Menor valor = mais urgente (vence a arbitragem) em ambos.

### O que NÃO é toggle

- **Remoção do safeguard de proporção** (`SAFE_GUARD_PROPORTION_FOR_COMPLETION_GWA`):
  intrínseco do engine refatorado — a saída do EV_GREEN é event-driven
  (`vehicle_get_next_tls`), substituindo o safeguard euclidiano. O safeguard antigo
  só existe no `greenwave_legacy`, congelado.
- **FSM de 3 fases** (`CLEARING → EV_GREEN → EXIT_YELLOW`): é o core do engine, não
  um plugin.
- **Visualização** (highlight de faixa + marker no TLS): toggle global ortogonal
  `HIGHLIGHT_ALLOCATIONS`, aplica a `greenwave` independentemente dos `GW_*`.

## 3. Tabela completa de melhorias (legacy → greenwave)

| # | Aspecto | `greenwave_legacy` | `greenwave` |
|---|---|---|---|
| 1 | **FSM** | 4-status acoplado: `INITIAL_TRANSITION`→`IN_PROGRESS`→`FINAL_TRANSITION`→`RETURN_TO_PROGRAM_ORIGINAL`, controlado por flag `change_transition` | 3-fase clean: `CLEARING`→`EV_GREEN`→`EXIT_YELLOW`. EV_GREEN é event-driven; yellows são time-gated por `TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT` |
| 2 | **Visualização** | nenhuma | Polígonos via TraCI: faixa prioritária + marker no TLS, cor por severidade (cyan = dreno). Toggle global `HIGHLIGHT_ALLOCATIONS` |
| 3 | **Prioridade** | deadline da missão | configurável via `GW_PRIORITY`: `deadline` ou `eta` |
| 4 | **Anti-flicker** | inexistente | `GW_ANTIFLICKER`: `MIN_EV_GREEN_HOLD` (lock-out de EV_GREEN recém-iniciado) + `PREEMPT_DELTA_THRESHOLD` (delta mínimo para preemptar) |
| 5 | **Fila de pendentes** | vencedor mata perdedor; perdedor re-pede do zero ("yellow gap") | `GW_PENDING_QUEUE`: fila priority-sorted no holder, hand-off sem reabrir programa original |
| 6 | **Safeguard de proporção** | `SAFE_GUARD_PROPORTION_FOR_COMPLETION_GWA` (proporção euclidiana ≥ 0.8) | removido (saída event-driven) |
| 7 | **Spillback** | inexistente | `GW_SPILLBACK`: `SpillbackDetector` BFS-by-depth a partir do TLS raiz do EV, expansão por `SPILLBACK_GRAPH_DEPTH` níveis. Drenos em saídas saturadas; skip por-TLS quando a saída do EV está bloqueada |
| 8 | **Arquitetura** | `TrafficManager` monolítico (287 linhas) | Strategy-pattern + composição por config; `PriorityPolicy` como slot plugável |

### Melhorias operacionais (globais — aplicam a todas as estratégias)

9. **CollisionManager com preservação seletiva do EV** — SUMO roda com
   `--collision.action warn`; o `CollisionManager` remove **manualmente** só os
   participantes civis, preservando EVs. Métricas em `tripinfo.csv` / `lanedata.csv`:
   `COLLISIONS_INVOLVED` (civis), `EV_COLLISIONS` (eventos com EV), `COLLISION_STEPS`.
10. **Cenário próximo do default-puro do SUMO** — car-follow `Krauss`, modelo
    lane-based (sem sublane), `randomTrips.py --fringe-factor 10`, vTypes minimal.
11. **Flags do SUMO** — `--time-to-teleport 180`, `--device.bluelight.reactiondist 40`.

## 4. Estudo de ablação

Cada experimento que o usuário quer comparar é uma combinação de config:

| Experimento | `.env` |
|---|---|
| Baseline puro SUMO | `ALGORITHM=baseline` |
| Greenwave original (referência) | `ALGORITHM=greenwave_legacy` |
| Greenwave + EDF puro | `ALGORITHM=greenwave GW_PRIORITY=deadline GW_ANTIFLICKER=false GW_PENDING_QUEUE=false GW_SPILLBACK=false` |
| Greenwave + EDF com distância (ETA) | `ALGORITHM=greenwave GW_PRIORITY=eta GW_ANTIFLICKER=false GW_PENDING_QUEUE=false GW_SPILLBACK=false` |
| Greenwave + EDF distância + anti-flicker | `ALGORITHM=greenwave GW_PRIORITY=eta GW_ANTIFLICKER=true GW_PENDING_QUEUE=false GW_SPILLBACK=false` |
| Greenwave + EDF puro + fila de pendentes | `ALGORITHM=greenwave GW_PRIORITY=deadline GW_ANTIFLICKER=false GW_PENDING_QUEUE=true GW_SPILLBACK=false` |
| Greenwave + EDF puro + spillback | `ALGORITHM=greenwave GW_PRIORITY=deadline GW_ANTIFLICKER=false GW_PENDING_QUEUE=false GW_SPILLBACK=true` |
| Greenwave completo (≡ antigo `shield`) | `ALGORITHM=greenwave` (defaults: `GW_PRIORITY=eta`, todos os toggles `true`) |

Os defaults do `greenwave` reproduzem exatamente o antigo `shield`.

### Métricas a comparar

| Eixo | Métrica | Fonte |
|---|---|---|
| Tempo de resposta | EVs salvas dentro do golden time / EVs despachadas | `tripinfo.csv` filtrado por `vType='emergency_emergency'`; `arrival - depart` vs `SEVERITY_GOLDEN_TIME[severity]` |
| Trânsito geral | Tempo médio de viagem dos civis | `tripinfo.csv` filtrado por `vType='krauss_or_eidm'`, média de `duration` |
| Segurança — civis | `COLLISIONS_INVOLVED` | qualquer linha do CSV (valor de fim de simulação) |
| Segurança — EV | `EV_COLLISIONS` | idem |

### Knobs adicionais

- `SPILLBACK_GRAPH_DEPTH` — profundidade da BFS do spillback (1 = só TLS raiz;
  2 = +1-hop; 3 = +2-hop). Só tem efeito com `GW_SPILLBACK=true`.
- `MIN_EV_GREEN_HOLD`, `PREEMPT_DELTA_THRESHOLD` — magnitude do anti-flicker. Só
  têm efeito com `GW_ANTIFLICKER=true`.
- `SEVERITY_ETA_PENALTY`, `MIN_SPEED_FLOOR_FOR_ETA` — parâmetros da policy `eta`.
- `HIGHLIGHT_ALLOCATIONS` — `false` em batch headless reduz custo TraCI.

## 5. Mapa de arquivos

```
src/sumotraci/managers/traffic/
├── manager.py                              # TrafficManager (entry point, delega à strategy)
├── green_wave.py                           # GreenWaveManager (FSM 3-fase + queue + anti-flicker + viz)
├── edf.py                                  # ArbitrationPolicy + EDFArbitration
├── priority.py                             # PriorityPolicy slot: DeadlinePriority, ETAPriority, make_priority_policy
├── spillback.py                            # SpillbackDetector (BFS-by-depth)
└── strategies/
    ├── base.py                             # TrafficControlStrategy ABC
    ├── baseline.py                         # NoOpStrategy ('baseline')
    ├── legacy_greenwave.py                 # LegacyGreenWaveStrategy ('greenwave_legacy', congelada)
    └── greenwave.py                        # GreenWaveStrategy ('greenwave', composta via GW_*)

src/sumotraci/managers/
└── collision_manager.py                    # global, aplica a todas as estratégias
```

## 6. Referências cruzadas

- `docs/SPILLBACK_PLAN.md` — design do spillback (Phase A) e da Phase B (mpc)
- `docs/MPC_PLAN.md` — Phase B (não implementada)
