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

O `greenwave` é parametrizado por chaves no `Settings` (variáveis de ambiente
ou `.env`):

| Config | Tipo | Valores | Papel |
|---|---|---|---|
| `GW_PRIORITY` | *policy slot* | `deadline` \| `eta` | Como calcular o valor de prioridade de um pedido de EV num TLS. Sempre exatamente um. |
| `GW_EV_PREEMPTION` | toggle | `true` \| `false` | Permite que um EV de maior prioridade preempte um TLS **já alocado a outro EV**. Só ocorre na fase `EV_GREEN` e a transição é sempre *graceful*. **Off por default** (controle rigoroso: a sucessão só acontece via hand-off natural). |
| `GW_ANTIFLICKER` | toggle | `true` \| `false` | Histerese sobre a preempção EV-EV — **só tem efeito com `GW_EV_PREEMPTION=true`**. Liga/desliga `MIN_EV_GREEN_HOLD` (protege os primeiros N s de `EV_GREEN`) + `PREEMPT_DELTA_THRESHOLD` (margem mínima de prioridade). Quando off, os dois são zerados. |
| `GW_SPILLBACK` | toggle | `true` \| `false` | Liga/desliga o detector de spillback BFS + mecanismo de drenos. |
| `GW_FAST_HANDOFF` | toggle | `true` \| `false` | No hand-off, promove o sucessor direto para `EV_GREEN` em vez de re-executar `CLEARING`. Off por default (conservador). |

A **fila de alocações pendentes com hand-off é intrínseca ao engine** (sempre
ligada): o perdedor da arbitragem é enfileirado no holder e assume no hand-off
natural — não é mais um toggle.

Combinações distintas dos toggles principais: como `GW_ANTIFLICKER` só tem efeito
quando `GW_EV_PREEMPTION=true`, são **4** combinações com preempção off
(`GW_PRIORITY × GW_SPILLBACK`) **+ 8** com preempção on
(`GW_PRIORITY × GW_ANTIFLICKER × GW_SPILLBACK`) = **12 distintas**.
`GW_FAST_HANDOFF` é ortogonal e só afeta o hand-off.

### Preempção concorrente entre EVs — `GW_EV_PREEMPTION`

O engine trabalha sob a filosofia de **controle rigoroso**: uma vez que um TLS é
alocado a um EV, nenhum outro EV o toma no meio do caminho. Quem perde a
arbitragem entra na fila e assume no hand-off natural. `GW_EV_PREEMPTION` abre uma
única exceção controlada.

| Fase do holder | `GW_EV_PREEMPTION=false` (default) | `GW_EV_PREEMPTION=true` |
|---|---|---|
| `CLEARING` | bloqueado (fila) | bloqueado (fila) |
| `EV_GREEN` (primeiros `MIN_EV_GREEN_HOLD` s) | bloqueado (fila) | bloqueado se `GW_ANTIFLICKER` (fila) |
| `EV_GREEN` (após o hold) | bloqueado (fila) | **preempta** (graceful) |
| `EXIT_YELLOW` | bloqueado (fila) | bloqueado (fila) |

Quando a preempção ocorre, a transição é **graceful**: o holder nunca é derrubado
com um pulo de volta ao programa base. Ele é levado a `EXIT_YELLOW` (amarelo de
segurança nas vias que estavam verdes) e, terminado o intervalo de segurança, o
hand-off natural promove o pendente de maior prioridade. Isso preserva a invariante
de segurança *nunca verde→verde sem amarelo*.

**Drenos** (`GW_SPILLBACK`) são independentes de `GW_EV_PREEMPTION`: qualquer EV
preempta um dreno imediatamente (drenos nunca são bloqueados).

### `GW_FAST_HANDOFF`

No hand-off (fila de pendentes não-vazia ao fim do `EXIT_YELLOW` do holder), o sucessor
hoje entra em `CLEARING` e espera mais `TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT` segundos.
Mas no instante do hand-off **toda aproximação não-EV já está vermelha** (esteve vermelha
durante todo o `EV_GREEN` + `EXIT_YELLOW` do predecessor) e a via do predecessor acabou
de ter um amarelo completo — ou seja, o `EXIT_YELLOW` do predecessor **já é** o inter-green
de clearance. Re-executar `CLEARING` apenas conta esse intervalo duas vezes (a escrita TraCI
é no-op; só sobra a espera). Com `GW_FAST_HANDOFF=true` o sucessor vai direto para `EV_GREEN`,
adiantando o verde do próximo EV em ~`TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT` segundos.

Trade-off: para um sucessor em via **conflitante** com o predecessor, zera-se a margem de
*all-red* entre o amarelo terminando e o verde conflitante começando (na prática segura, pois
a aproximação conflitante já estava parada e a do predecessor já teve amarelo completo). É um
candidato natural a ablação: comparar `EV_COLLISIONS` (CollisionManager) e tempo de viagem dos
EVs com o toggle on/off.

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
| 4 | **Preempção EV-EV** | vencedor mata perdedor a qualquer momento (causa flicker) | `GW_EV_PREEMPTION` (off por default): preempção só em `EV_GREEN` e **graceful** (holder → `EXIT_YELLOW` → hand-off, sem pulo ao programa base). `CLEARING`/`EXIT_YELLOW` sempre bloqueados |
| 5 | **Anti-flicker** | inexistente | `GW_ANTIFLICKER` (histerese sobre a preempção EV-EV): `MIN_EV_GREEN_HOLD` (protege o início do `EV_GREEN`) + `PREEMPT_DELTA_THRESHOLD` (delta mínimo). Só atua com `GW_EV_PREEMPTION=true` |
| 6 | **Fila de pendentes + hand-off** | vencedor mata perdedor; perdedor re-pede do zero ("yellow gap") | **intrínseco** (sempre on): fila priority-sorted no holder, hand-off sem reabrir programa original |
| 7 | **Safeguard de proporção** | `SAFE_GUARD_PROPORTION_FOR_COMPLETION_GWA` (proporção euclidiana ≥ 0.8) | removido (saída event-driven) |
| 8 | **Spillback** | inexistente | `GW_SPILLBACK`: `SpillbackDetector` semeado pelo **corredor do EV** (todos os TLSs na rota dentro do range), com BFS opcional `SPILLBACK_GRAPH_DEPTH` níveis a jusante. Dreno genérico das saídas saturadas (escoa o pulso do green wave e protege as transversais que o EV não usa); skip por-TLS quando a saída do EV está bloqueada |
| 9 | **Arquitetura** | `TrafficManager` monolítico (287 linhas) | Strategy-pattern + composição por config; `PriorityPolicy` como slot plugável |

### Melhorias operacionais (globais — aplicam a todas as estratégias)

10. **CollisionManager com preservação seletiva do EV** — SUMO roda com
   `--collision.action warn`; o `CollisionManager` remove **manualmente** só os
   participantes civis, preservando EVs. Métricas em `tripinfo.csv` / `lanedata.csv`:
   `COLLISIONS_INVOLVED` (civis), `EV_COLLISIONS` (eventos com EV), `COLLISION_STEPS`.
11. **Cenário próximo do default-puro do SUMO** — car-follow `Krauss`, modelo
    lane-based (sem sublane), `randomTrips.py --fringe-factor 10`, vTypes minimal.
12. **Flags do SUMO** — `--time-to-teleport 180`, `--device.bluelight.reactiondist 40`.

## 4. Estudo de ablação

Cada experimento que o usuário quer comparar é uma combinação de config:

| Experimento | `.env` |
|---|---|
| Baseline puro SUMO | `ALGORITHM=baseline` |
| Greenwave original (referência) | `ALGORITHM=greenwave_legacy` |
| Greenwave rigoroso + EDF puro | `ALGORITHM=greenwave GW_PRIORITY=deadline GW_EV_PREEMPTION=false GW_SPILLBACK=false` |
| Greenwave rigoroso + ETA (**default**) | `ALGORITHM=greenwave` (defaults: `GW_PRIORITY=eta`, `GW_EV_PREEMPTION=false`, `GW_SPILLBACK=false`) |
| Greenwave + preempção EV-EV (sem histerese) | `ALGORITHM=greenwave GW_PRIORITY=eta GW_EV_PREEMPTION=true GW_ANTIFLICKER=false GW_SPILLBACK=false` |
| Greenwave + preempção EV-EV + anti-flicker | `ALGORITHM=greenwave GW_PRIORITY=eta GW_EV_PREEMPTION=true GW_ANTIFLICKER=true GW_SPILLBACK=false` |
| Greenwave rigoroso + spillback | `ALGORITHM=greenwave GW_PRIORITY=eta GW_EV_PREEMPTION=false GW_SPILLBACK=true` |
| Greenwave + preempção EV-EV + spillback (≈ antigo `shield`) | `ALGORITHM=greenwave GW_EV_PREEMPTION=true GW_SPILLBACK=true` |
| Qualquer combinação acima + fast hand-off | `... GW_FAST_HANDOFF=true` |

> **Mudança de default (2026-05-20):** os defaults do `greenwave` **não**
> reproduzem mais o antigo `shield`. O default agora é **controle rigoroso** —
> `GW_EV_PREEMPTION=false` (sem preempção concorrente entre EVs) e
> `GW_SPILLBACK=false`. Para algo próximo do `shield` antigo (que preemptava e
> drenava), use `GW_EV_PREEMPTION=true GW_SPILLBACK=true`. A fila de pendentes +
> hand-off, que no `shield` era um toggle, agora é intrínseca (sempre ligada).

### Métricas a comparar

| Eixo | Métrica | Fonte |
|---|---|---|
| Tempo de resposta | EVs salvas dentro do golden time / EVs despachadas | `tripinfo.csv` filtrado por `vType='emergency_emergency'`; `arrival - depart` vs `SEVERITY_GOLDEN_TIME[severity]` |
| Trânsito geral | Tempo médio de viagem dos civis | `tripinfo.csv` filtrado por `vType='krauss_or_eidm'`, média de `duration` |
| Segurança — civis | `COLLISIONS_INVOLVED` | qualquer linha do CSV (valor de fim de simulação) |
| Segurança — EV | `EV_COLLISIONS` | idem |

### Knobs adicionais

- `SPILLBACK_GRAPH_DEPTH` — quantos saltos a BFS expande **além do corredor do EV**
  (1 = só o corredor; 2 = +1-hop a jusante, pega cascata; 3 = +2-hop). Só tem
  efeito com `GW_SPILLBACK=true`.
- `DRAIN_MAX_DURATION` — teto de segurança (s) para um único dreno em verde.
- `DRAIN_COOLDOWN` — após um dreno terminar **pelo teto** sem ter esvaziado a via
  (caso patológico de via cronicamente saturada), bloqueia um novo dreno naquele
  TLS por este tempo. Evita o flapping amarelo↔verde e dá verde às outras
  aproximações. Drenos que esvaziaram a via (saída por histerese de ocupação) não
  são penalizados.
- `MIN_EV_GREEN_HOLD`, `PREEMPT_DELTA_THRESHOLD` — magnitude do anti-flicker. Só
  têm efeito com `GW_EV_PREEMPTION=true` **e** `GW_ANTIFLICKER=true`.
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
