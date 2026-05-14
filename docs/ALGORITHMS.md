# Algoritmos de controle e ablação

Este documento descreve os algoritmos de controle de tráfego implementados no
projeto, as melhorias incrementais que foram introduzidas em relação à versão
original do *green-wave*, e como executar o estudo de ablação que isola a
contribuição de cada melhoria.

> Toda strategy implementa a interface `TrafficControlStrategy` e é selecionada
> em tempo de execução via `Settings.ALGORITHM` (variável de ambiente
> `ALGORITHM` ou direto em `.env`).

## 1. Algoritmos avaliados

| `ALGORITHM` | Strategy | Papel no estudo |
|---|---|---|
| `default` | `NoOpStrategy` | Baseline absoluto: controle de tráfego padrão do SUMO, sem qualquer preempção para EVs. |
| `legacy_greenwave` | `LegacyGreenWaveStrategy` | Versão original do green-wave (commit `664cef5`), pré-refactor. Mantida verbatim como ponto de partida da ablação. |
| `fsm_greenwave` | `FSMGreenWaveStrategy` | Adiciona ao legacy **apenas** as melhorias estruturais (FSM 3-fase + visualização). Mantém arbitragem por deadline e descarta perdedores (sem fila). |
| `edf_greenwave` (alias `proposto`) | `EDFGreenWaveStrategy` | Adiciona priorização por ETA, fila pendente com hand-off, e anti-flicker em cima do FSM. **Sem** spillback shield. |
| `shield` | `SpillbackAwareEDFGreenWaveStrategy` | Adiciona o spillback shield (BFS por profundidade) em cima do edf_greenwave. Versão final / Phase A completa. |
| `mpc` | — (Phase B) | Não implementado. Ver `docs/MPC_PLAN.md`. |

### Ordenação por incremento de funcionalidade

```
default
  └─ + preempção verde (FSM 4-status, deadline-based)
      = legacy_greenwave
          └─ + FSM 3-fase clean + visualização
              = fsm_greenwave
                  └─ + ETA + queue + anti-flicker
                      = edf_greenwave
                          └─ + spillback shield BFS
                              = shield
```

Cada degrau isola a contribuição de **uma classe de melhoria**, permitindo
quantificar o efeito de cada uma separadamente nos experimentos.

## 2. Tabela completa de melhorias (legacy → shield)

| # | Aspecto | `legacy_greenwave` | `fsm_greenwave` | `edf_greenwave` | `shield` |
|---|---|---|---|---|---|
| 1 | **FSM** | 4-status acoplado: `INITIAL_TRANSITION`→`IN_PROGRESS`→`FINAL_TRANSITION`→`RETURN_TO_PROGRAM_ORIGINAL`, controlado por flag `change_transition` | 3-fase clean: `CLEARING`→`EV_GREEN`→`EXIT_YELLOW`. EV_GREEN é event-driven (sai quando EV passa via `vehicle_get_next_tls`); yellows são time-gated por `TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT` | ✓ (igual fsm) | ✓ (igual fsm) |
| 2 | **Visualização** | nenhuma | Polígonos coloridos via TraCI: faixa prioritária (linha) + marker no TLS (preenchido), cor por severidade do EV (cyan reservado para drains do shield). Toggle global via `HIGHLIGHT_ALLOCATIONS` | ✓ (igual fsm) | ✓ (igual fsm) |
| 3 | **Prioridade / arbitragem** | Deadline da missão (`SEVERITY_GOLDEN_TIME[severity]`); EV crítico mas distante derruba EV leve mas próximo | Deadline da missão (igual legacy) | ETA-based: `priority_value = distance / max(speed, MIN_SPEED_FLOOR_FOR_ETA) + SEVERITY_ETA_PENALTY[severity]`. Proximidade domina, severidade é desempate fino | ✓ (igual edf) |
| 4 | **Anti-flicker** | inexistente — qualquer novo requester com deadline melhor preempta o atual recém-iniciado | inexistente (igual legacy) | Duas camadas: `MIN_EV_GREEN_HOLD` (5s lock-out após entrar EV_GREEN — drains exclusos) + `PREEMPT_DELTA_THRESHOLD` (novo precisa ser ≥2s melhor pra preemptar) | ✓ (igual edf) |
| 5 | **Fila pendente / hand-off** | Vencedor mata perdedor cortando-o pra `FINAL_TRANSITION`. Perdedor não retém estado nenhum, espera vencedor restaurar e re-pede do zero (`INITIAL_TRANSITION` outra vez) → "yellow gap" entre EVs sucessivos | Loser é descartado (igual legacy, sem queue). Pode re-requisitar no próximo tick | Pending queue priority-sorted no holder. Ao terminar naturalmente, próximo da fila assume o TLS sem reabrir programa original (zero gap) | ✓ (igual edf) |
| 6 | **Safeguard de proporção** | `SAFE_GUARD_PROPORTION_FOR_COMPLETION_GWA` — proporção da distância euclidiana percorrida ≥ 0.8 → não preemptável. Frágil em rotas curvas | removido (saída natural via `vehicle_get_next_tls`) | removido (igual fsm) | removido (igual fsm) |
| 7 | **Spillback awareness** | inexistente — sinal abre, mas se a saída do EV está saturada, EV trava no cruzamento sem progredir | inexistente | inexistente | `SpillbackDetector` BFS-by-depth a partir do TLS imediato do EV (raiz), expansão por `SPILLBACK_GRAPH_DEPTH=2` níveis via outgoing-edges. Drains abertos em saídas saturadas (transversais inclusive). Skip por-TLS quando saída do EV está bloqueada |
| 8 | **Arquitetura** | `TrafficManager` monolítico de 287 linhas | Strategy-pattern: `TrafficControlStrategy` ABC + plugáveis | ✓ (igual fsm) | ✓ (igual fsm) |

### Melhorias operacionais (globais — aplicam a todas as strategies)

Estas melhorias estão no nível do `SimulationEngine` e do cenário SUMO; valem
para qualquer `ALGORITHM` selecionado.

9. **CollisionManager com preservação seletiva do EV**
   - SUMO roda com `--collision.action warn` (logando colisões mas sem remover veículos automaticamente)
   - O `CollisionManager` lê `getCollidingVehiclesIDList()` a cada step e remove **manualmente** apenas os participantes civis; o EV é preservado para que `EmergencyManager` e chamadas TraCI subsequentes continuem operando
   - Métricas exportadas em `tripinfo.csv` e `lanedata.csv`:
     - `COLLISIONS_INVOLVED` — civis removidos por colisão (qualquer causa)
     - `EV_COLLISIONS` — eventos distintos com participação do EV
     - `COLLISION_STEPS` — número de passos com ≥1 colisão registrada

10. **Cenário próximo do default-puro do SUMO**
    - Modelo car-follow `Krauss` (collision-free por construção)
    - Modelo lane-based padrão (sem sublane — elimina colisões laterais)
    - `randomTrips.py --fringe-factor 10` (próximo do default 1.0; OD distribuída em vez de só fringes)
    - vTypes minimal (apenas `id`, `carFollowModel`, `color` para civis; EV mantém `vClass=emergency`, `speedFactor=1.2`, devices necessários)
    - Justificativa metodológica: o trabalho é sobre **otimização de algoritmos de controle**, não engenharia de tráfego. Manter o cenário próximo do default reduz superfície de questionamento metodológico.

11. **Flags adicionais do SUMO**
    - `--time-to-teleport 180` — recovery mais rápido de jams residuais sem mudar comportamento de driver
    - `--device.bluelight.reactiondist 40` — civis começam a reagir ao EV a 40m
    - `--no-turnarounds=true` na geração da rede

## 3. Como executar o estudo de ablação

### Variáveis de ambiente recomendadas (`.env`)

```bash
# fixar o cenário
GRID_NUMBER=5
LANE_LENGTH=300.0
LANE_NUMBER=3
VEHICLE_NUMBER=4800
SIMULATION_END_TIME=900.0

# o que varia entre rodadas
ALGORITHM=default      # ← alterar pra cada algoritmo: default, legacy_greenwave, fsm_greenwave, edf_greenwave, shield
SEED=217492            # ou iterar pelos 10 SEEDS já configurados em config.py
```

### Loop de execução sugerido

```bash
for algo in default legacy_greenwave fsm_greenwave edf_greenwave shield; do
  for seed_idx in 0 1 2 3 4 5 6 7 8 9; do
    ALGORITHM=$algo SEED_INDEX=$seed_idx uv run python -m sumotraci ...
    # mover/renomear data/tripinfo.csv e data/lanedata.csv para preservar
  done
done
```

(adapte ao seu wrapper de execução — o ponto é: os 10 seeds × 5 algoritmos = 50 corridas).

### Métricas a comparar entre algoritmos

| Eixo | Métrica | Fonte |
|---|---|---|
| **Tempo de resposta** | EVs salvas dentro do golden time / EVs despachadas | `tripinfo.csv` filtrado por `vType='emergency_emergency'`; comparar `arrival - depart` contra `SEVERITY_GOLDEN_TIME[severity]` |
| **Trânsito geral** | Tempo médio de viagem dos civis | `tripinfo.csv` filtrado por `vType='krauss_or_eidm'`, média de `duration` |
| **Segurança — civis** | `COLLISIONS_INVOLVED` total | qualquer linha de `tripinfo.csv` (valor de fim de simulação repetido) |
| **Segurança — EV** | `EV_COLLISIONS` total | idem acima |

### Comparações esperadas (hipóteses)

| Comparação | O que testa | Hipótese |
|---|---|---|
| `default` vs `legacy_greenwave` | Valor do greenwave em si | Greenwave ↑ saves, ≈ trânsito, ↑ EV_collisions (EV passa em vermelho com mais frequência) |
| `legacy_greenwave` vs `fsm_greenwave` | Valor do refactor estrutural (FSM clean) | FSM clean: ≈ saves (mesma lógica de arbitração), efeito sutil em transitions, sem mudança em segurança |
| `fsm_greenwave` vs `edf_greenwave` | Valor de ETA + queue + anti-flicker | ETA: ↑ saves (proximidade domina); anti-flicker: ↓ chaveamento desnecessário; queue: zero "yellow gap" entre EVs |
| `edf_greenwave` vs `shield` | Valor isolado do spillback shield | ↑ saves em cenários congestionados (EV não trava em junções com saída saturada); pode ↑ trânsito civil pelos drains; ↓ EV_collisions por melhor preparação dos cruzamentos |

### Knobs para ablação fina dentro de uma strategy

- **Spillback profundidade** (`shield` apenas): `SPILLBACK_GRAPH_DEPTH=1` desliga cascata; `=2` (default) cobre 1-hop; `=3` cobre 2-hop. Em grid 5×5: depth=2 ≈ 5 TLSs, depth=3 ≈ 17.
- **Anti-flicker** (`edf_greenwave`/`shield`): zerar `MIN_EV_GREEN_HOLD=0` e `PREEMPT_DELTA_THRESHOLD=0` desliga as duas camadas de anti-flicker.
- **Highlight visual**: `HIGHLIGHT_ALLOCATIONS=False` em batch headless reduz custo TraCI (50 corridas × ~900 steps cada).

## 4. Mapa de arquivos

```
src/sumotraci/managers/traffic/
├── manager.py                              # TrafficManager (entry point, delega à strategy)
├── green_wave.py                           # GreenWaveManager (FSM 3-fase + queue + anti-flicker + viz, usado por edf_greenwave/shield)
├── edf.py                                  # ArbitrationPolicy + EDFArbitration
├── spillback.py                            # SpillbackDetector (BFS-by-depth)
└── strategies/
    ├── base.py                             # TrafficControlStrategy ABC
    ├── default.py                          # NoOpStrategy ('default')
    ├── legacy_greenwave.py                 # LegacyGreenWaveStrategy ('legacy_greenwave')
    ├── fsm_greenwave.py                    # FSMGreenWaveStrategy ('fsm_greenwave')
    ├── edf_greenwave.py                    # EDFGreenWaveStrategy ('edf_greenwave', 'proposto')
    └── spillback_shield.py                 # SpillbackAwareEDFGreenWaveStrategy ('shield')

src/sumotraci/managers/
└── collision_manager.py                    # global, aplica a todas as strategies
```

## 5. Referências cruzadas

- `docs/SPILLBACK_PLAN.md` — Phase A (shield) e Phase B (mpc) detalhes de design
- `docs/MPC_PLAN.md` — Phase B (não implementada)
