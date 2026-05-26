1. Máquina de estados (FSM)
Antes: 4 estados lineares: INITIAL_TRANSITION → IN_PROGRESS → FINAL_TRANSITION → RETURN_TO_PROGRAM_ORIGINAL. As transições eram sempre temporizadas (time‑gated).

Agora: 3 fases: CLEARING → EV_GREEN → EXIT_YELLOW.

CLEARING e EXIT_YELLOW usam o mesmo timer (T_clear), mas EV_GREEN é event‑driven (veículo sair do alcance do semáforo ou ocupação de dreno cair).

Isso elimina os estados redundantes antigos (INITIAL_TRANSITION / FINAL_TRANSITION) e permite saída imediata do verde sem esperar um timeout fixo.

2. Política de prioridade
Antes: Prioridade baseada apenas no deadline (deadline menor = mais urgente). O atributo severity era armazenado mas não utilizado na decisão (havia um bloco comentado no legado).

Agora: A prioridade é configurável via GW_PRIORITY ("deadline" ou "eta"). O valor priority_value é calculado dinamicamente (ETA = distância / velocidade atual) e usado em toda a arbitragem.

3. Arbitragem e preempção
Antes:

Critério de preempção: deadline menor + barreira espacial (SAFE_GUARD_PROPORTION_FOR_COMPLETION_GWA).

Se um veículo mais urgente aparecia, o atual era forçado a FINAL_TRANSITION (e depois removido). Não havia “lock‑out” temporal.

Se o atual já tivesse completado uma proporção da distância euclidiana até o semáforo, não era preemptável.

Agora:

Arbitragem delegada a uma classe ArbitrationPolicy (por exemplo EDFArbitration com delta).

Controle rigoroso por default (GW_EV_PREEMPTION=False): uma vez que um TLS é alocado a um EV, nenhum outro EV o preempta — o desafiante entra na fila e assume só no hand‑off natural.

Preempção concorrente entre EVs (GW_EV_PREEMPTION=True): permite que um EV de maior prioridade preempte, mas SÓ na fase EV_GREEN (CLEARING e EXIT_YELLOW permanecem bloqueados). A transição é sempre graceful — o holder vai para EXIT_YELLOW (amarelo de segurança) e o hand‑off promove o desafiante após o intervalo de segurança, nunca há pulo de volta ao programa base.

Anti‑flicker (GW_ANTIFLICKER, histerese — só tem efeito com GW_EV_PREEMPTION=True):

PREEMPT_DELTA_THRESHOLD – o novo precisa ser ao menos delta segundos melhor no priority_value.

MIN_EV_GREEN_HOLD – o holder fica “travado” no EV_GREEN por N segundos iniciais (não pode ser preemptado).

A barreira espacial euclidiana foi totalmente removida.

Quando GW_ANTIFLICKER=False, ambos os parâmetros são zerados, virando um EDF puro (comportamento mais próximo do legado, mas ainda sem a barreira espacial).

4. Fila de espera (pending queue)
Antes: Perdedor é descartado; precisa ser re‑solicitado no próximo tick.

Agora (intrínseca, sempre ligada — não é mais um toggle):

Perdedores da arbitragem entram em uma fila ordenada por prioridade no próprio holder.

Quando o holder termina (naturalmente ou por preempção graceful), se houver um próximo pendente ainda relevante, a alocação é passada diretamente para ele (hand‑off), sem restaurar o programa original.

A fila é limpa a cada tick (só reaparece quem continuar solicitando), funcionando como um mecanismo de stale‑guard.

5. Spillback / dreno
Antes: Sem nenhum tratamento de congestionamento.

Agora:

GW_SPILLBACK=True ativa um SpillbackDetector que usa BFS para encontrar edges saturados a montante.

Para cada saturado, cria um dreno (requester_id = "drain:<edge>") que aloca o semáforo com prioridade DRAIN_PRIORITY_VALUE.

O dreno usa lógica de saída baseada em ocupação (histerese) e um DRAIN_MAX_DURATION.

Se a via de saída do próprio EV estiver saturada, a preempção do EV é pulada (o dreno cuidará daquele semáforo, pois sinal verde para o EV seria inútil).

6. Destaque visual (highlight)
Antes: Nenhum overlay visual.

Agora: Se HIGHLIGHT_ALLOCATIONS=True, são desenhados polígonos sobre as faixas da via prioritária e um marcador no cruzamento, coloridos por severidade ou azul ciano para drenos.

7. Estrutura das alocações
Antes: _LegacyAllocation com campos como starting_position, arrival_position, next_edges, usados exclusivamente para a proporção euclidiana.

Agora: _Allocation armazena priority_edge, phase, wait_until, ev_green_started_at, lista pending, highlight_polygon_ids – nada de geometria.

8. Gerenciamento do laço principal
Antes: Itera de trás para frente removendo itens com .pop(key), o que é frágil com índices.

Agora: Constrói uma lista de survivors a cada tick(), evitando alterações durante a iteração. A remoção de alocações terminadas é segura e clara.

9. Restauração e hand‑off
Antes: Ao sair (RETURN_TO_PROGRAM_ORIGINAL), sempre restaurava o programa original e depois removia a alocação.

Agora:

Se há um próximo pendente, o programa não é restaurado; a nova fase CLEARING é iniciada diretamente.

Só se restaura o programa quando a fila realmente esvazia.

10. Tratamento de erros (TraCI)
Ambos capturam exceções, mas o novo é mais granular (ex: ignora polígonos que não podem ser removidos, trata falhas ao obter ocupação de faixa, etc.). O legado já havia introduzido proteções; o novo as mantém e expande.

11. Separação de responsabilidades
Antes: Toda a lógica (FSM, arbitration, store, restore) residia em um único arquivo/classe.

Agora: A estratégia é composta por várias classes independentes:

GreenWaveStrategy (ponto de entrada, itera EVs, chama request)

GreenWaveManager (FSM, alocações, hand‑off)

PriorityPolicy (cálculo do valor de prioridade)

SpillbackDetector (detecção de spillback)

EDFArbitration (política de arbitragem)
Isso torna cada peça testável isoladamente e permite os 16 combos de features via Settings.