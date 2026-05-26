# Visão geral

O projeto evoluiu de uma comparação binária (Green Wave vs. baseline padrão do SUMO) para um framework de simulação focado em avaliar estratégias de preempção de veículos de emergência (EV) sobre SUMO + TraCI. Toda a arquitetura foi reorganizada em torno de três estratégias comparáveis, executando o mesmo cenário, e de uma camada de composição por configuração que viabiliza estudos de ablação sobre cada melhoria do Green Wave isoladamente.

# Três estratégias

- **baseline** — programa de sinalização padrão do SUMO. Os ciclos programados rodam intactos e EVs não recebem prioridade. Piso absoluto de comparação.
- **greenwave_legacy** — versão original do Green Wave, congelada como ponto de comparação. Mantém a máquina de estados de 4 estados (INITIAL_TRANSITION → IN_PROGRESS → FINAL_TRANSITION → RETURN_TO_PROGRAM_ORIGINAL), arbitragem EDF por deadline cru (derivado da severidade via SEVERITY_GOLDEN_TIME), sem fila de pendentes, sem anti-flicker, sem spillback. Mantém também o safeguard euclidiano: um EV que já percorreu ≥ 80% da distância até o TLS não pode ser destituído da preempção, mesmo por um EV mais urgente.
- **greenwave** — engine refatorado. Implementa máquina de estados de 3 fases (CLEARING → EV_GREEN → EXIT_YELLOW), prioridade plugável (deadline cru ou ETA + penalidade por severidade), anti-flicker em duas camadas, fila de pendentes com hand-off direto, spillback BFS com drenos em saídas saturadas, e destaque visual via polígonos TraCI nas vias e TLSs envolvidos na preempção (toggle HIGHLIGHT_ALLOCATIONS).

# Composição por configuração (GW_*)

A grande virada da refatoração: a estratégia greenwave é parametrizada por chaves no Settings, eliminando a explosão de classes anterior (uma por combinação de melhoria) e permitindo ablação direta via .env:

|      Config       |    Tipo     |    Valores     |                                 Função                                  |
|-------------------|-------------|----------------|-------------------------------------------------------------------------|
| GW_PRIORITY       | policy slot | deadline \| eta | Métrica de arbitragem (sempre exatamente uma)                           |
| GW_EV_PREEMPTION  | toggle      | true \| false   | Preempção concorrente entre EVs (só em EV_GREEN, graceful). Off = controle rigoroso |
| GW_ANTIFLICKER    | toggle      | true \| false   | Histerese sobre a preempção EV-EV (MIN_EV_GREEN_HOLD + PREEMPT_DELTA_THRESHOLD); só atua com GW_EV_PREEMPTION=true |
| GW_SPILLBACK      | toggle      | true \| false   | Liga o detector BFS e o mecanismo de drenos                             |

A fila de pendentes com hand-off direto é intrínseca ao engine (sempre ligada), não mais um toggle. Como GW_ANTIFLICKER só tem efeito com GW_EV_PREEMPTION=true, são 12 combinações distintas (4 com preempção off + 8 com preempção on), todas construíveis via .env. O default é controle rigoroso: GW_PRIORITY=eta, GW_EV_PREEMPTION=false, GW_SPILLBACK=false — nenhum EV preempta uma alocação em progresso.

# Arquitetura e código

A refatoração aplicou padrão Strategy (uma classe por algoritmo) combinada com composição via configuração (toggles que alteram comportamento sem nova classe). O green_wave.py original foi decomposto em módulos coesos: priority.py (slot de prioridade), edf.py (arbitragem), spillback.py (detector BFS), e o próprio green_wave.py passou a ser o engine FSM.

```
src/sumotraci/
├── main.py                                # entry point CLI (Typer)
├── core/
│   ├── simulation.py                      # SimulationEngine
│   ├── config.py                          # Settings (Pydantic)
│   └── sumo_interface.py                  # wrapper tipado de TraCI
└── managers/
    ├── accident_manager.py                # ciclo de vida de acidentes
    ├── emergency_manager.py               # dispatch e monitoramento de EVs
    ├── collision_manager.py               # colisões com preservação seletiva do EV
    └── traffic/
        ├── manager.py                     # TrafficManager (facade, delega à strategy)
        ├── green_wave.py                  # GreenWaveManager: FSM 3-fase + fila + anti-flicker + viz
        ├── edf.py                         # ArbitrationPolicy + EDFArbitration
        ├── priority.py                    # PriorityPolicy slot: DeadlinePriority, ETAPriority
        ├── spillback.py                   # SpillbackDetector (BFS-by-depth)
        └── strategies/
            ├── base.py                    # TrafficControlStrategy (ABC)
            ├── baseline.py                # NoOpStrategy
            ├── legacy_greenwave.py        # LegacyGreenWaveStrategy (congelada)
            ├── greenwave.py               # GreenWaveStrategy (composta via GW_*)
            └── __init__.py                # make_strategy()
```

# Máquina de estados de 3 fases

Cada alocação no GreenWaveManager (uma alocação = um requerente segurando prioridade em um TLS) atravessa três fases:

1. **CLEARING** — amarelo nas verdes conflitantes, preserva o estado da via do EV; espera TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT segundos (default: 8s) para desafogar a interseção antes de liberar verde ao EV.
2. **EV_GREEN** — verde para a via do EV, vermelho no resto; saída é event-driven: a cada tick verifica via vehicle_get_next_tls se o EV ainda está dentro de VEHICLE_DISTANCE_TO_TLS do TLS. Quando o EV passa, transita para EXIT_YELLOW.
3. **EXIT_YELLOW** — amarelo nas faixas que estavam verdes para o EV; espera TLJ_PHASE_RED_TO_GREEN_DURATION_LIMIT segundos; depois restaura o programa original do TLS ou faz hand-off direto para o próximo requerente pendente, sem reabrir o programa original.

# Arbitragem, preempção EV-EV e fila de pendentes

Quando dois EVs disputam o mesmo TLS, o engine opera por default em **controle rigoroso**: uma vez alocado a um EV, o TLS não é preemptado por outro. O perdedor da arbitragem entra na fila e assume no hand-off natural. `GW_EV_PREEMPTION=true` abre uma exceção controlada.

- **Fila de pendentes** (intrínseca, sempre ligada): requerentes que perderam a arbitragem entram na fila do holder, ordenada por prioridade. Quando o holder termina naturalmente, o próximo da fila é promovido diretamente para CLEARING (hand-off direto), sem reabrir o programa original do TLS — economiza o round-trip de setProgram e mantém a continuidade da preempção. A fila é re-snapshotada a cada tick a partir das chamadas request() da strategy, garantindo freshness (EVs que saíram do range não reaparecem na fila).
- **Preempção concorrente entre EVs** (GW_EV_PREEMPTION): só permite preemptar o holder na fase **EV_GREEN** — em CLEARING e EXIT_YELLOW o holder permanece bloqueado (o desafiante apenas enfileira). Quando ocorre, a transição é **graceful**: o holder é levado a EXIT_YELLOW (amarelo de segurança) e o hand-off natural promove o desafiante de maior prioridade após o intervalo de segurança — nunca há pulo de volta ao programa base (invariante de segurança *nunca verde→verde sem amarelo*).
- **Arbitragem EDF** (EDFArbitration.can_preempt): o desafiante vence se new_priority + PREEMPT_DELTA_THRESHOLD ≤ existing_priority. Menor priority_value = mais urgente.
- **Anti-flicker** (GW_ANTIFLICKER, histerese — só tem efeito com GW_EV_PREEMPTION=true): MIN_EV_GREEN_HOLD protege os primeiros N segundos da fase EV_GREEN contra preempção; PREEMPT_DELTA_THRESHOLD exige que o desafiante seja pelo menos delta mais urgente, evitando trocas instáveis em pequenas variações de ETA. Quando off, ambos são zerados (preempta desde o início do EV_GREEN, com margem estrita).
- **Drenos** (GW_SPILLBACK): independentes de GW_EV_PREEMPTION — qualquer EV preempta um dreno imediatamente.

# Spillback (GW_SPILLBACK)

O SpillbackDetector é semeado pelo **corredor do EV** — todos os TLSs na rota dentro de VEHICLE_DISTANCE_TO_TLS — e opcionalmente expande BFS por SPILLBACK_GRAPH_DEPTH saltos a jusante do corredor. Para cada vértice visitado, verifica a ocupação das saídas via lane_get_last_step_occupancy e classifica como saturada se ultrapassa SPILLBACK_OCCUPANCY_THRESHOLD. Em cada saída saturada:

- Um pedido de dreno (request_drain) é registrado no TLS **a jusante** da via saturada (o que controla a saída dela), abrindo verde para escoá-la até a ocupação cair abaixo de SPILLBACK_OCCUPANCY_RELEASE_THRESHOLD (histerese), ou até atingir o teto de segurança DRAIN_MAX_DURATION. Isso escoa o pulso despejado pelo green wave e desafoga as transversais que o EV não usa mas que, saturadas, bloqueariam o cruzamento dele (junction blocking).
- Se a saída saturada for a **própria saída do EV** naquele TLS (on_ev_path), a preempção do EV ali é suprimida (não-óbvio: não basta drenar — abrir verde para o EV rumo a uma via já lotada só piora o spillback).

A profundidade governa a cascata: depth=1 cobre só o corredor; depth≥2 também abre os TLSs a jusante de uma saída cuja própria saída seguinte está cheia, criando um corredor de vazão contínuo em vez de só empurrar o engarrafamento um quarteirão adiante.

Anti-flapping: se um dreno termina pelo teto DRAIN_MAX_DURATION sem ter esvaziado a via (via cronicamente saturada), aplica-se um cooldown (DRAIN_COOLDOWN) que bloqueia um novo dreno naquele TLS por um tempo — evitando o liga-desliga amarelo↔verde e cedendo verde às outras aproximações. Drenos que esvaziaram a via (saída por histerese de ocupação) não sofrem cooldown.

Drenos não competem com EVs por valor numérico: a precedência é estrutural (qualquer EV preempta um dreno; um dreno nunca preempta um EV) e independe de DRAIN_PRIORITY_VALUE e da policy GW_PRIORITY. Entre si, os drenos resolvem por FCFS + fila.

# Tratamento de colisões (global, vale para todas as estratégias)

O CollisionManager aplica preservação seletiva do EV, evitando que o tratamento padrão do SUMO quebre a continuidade da simulação:

- O SUMO roda com --collision.action teleport/warn, apenas registrando o evento sem remover participantes;
- O CollisionManager remove manualmente apenas os participantes civis, garantindo que EVs envolvidos em colisão permaneçam na simulação para que o EmergencyManager continue rastreando-os;
- Métricas exportadas no tripinfo.csv / lanedata.csv:
  - COLLISIONS_INVOLVED — número de civis removidos;
  - EV_COLLISIONS — número de eventos envolvendo um EV;
  - COLLISION_STEPS — número de steps com colisão registrada.

# Cenário de simulação

A simulação foi simplificada para isolar o efeito dos algoritmos de controle, evitando engenharia de tráfego como variável confundente:

- Modelo de car-following Krauss (livre de colisão por construção em condições normais);
- Modelo lane-based (sem --lateral-resolution / sublane);
- Geração de tráfego com randomTrips.py --fringe-factor 10;
- vTypes minimais; flags principais: --time-to-teleport 60, --device.bluelight.reactiondist 40.

A escolha de Krauss (em vez de EIDM + sublane do cenário anterior) foi motivada por dois fatores: Krauss não permite colisões espontâneas — isolando colisões verdadeiramente atribuíveis ao algoritmo (ex.: EV forçando passagem sob bluelight); e o modelo lane-based eliminou o ruído de colisões laterais que dominava as métricas anteriormente.
