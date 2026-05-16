A refatoração preserva **exatamente o mesmo comportamento em condições normais** (quando nenhuma chamada ao TraCI falha e não há divisão por zero). Porém, você introduziu algumas proteções que alteram o comportamento **nos cenários de erro**. Como o cabeçalho do código refatorado diz “Behaviour preserved verbatim”, vale destacar onde isso não é 100% verdade.

## Diferenças encontradas

### 1. Tratamento de exceções do TraCI
O código legado **não captura** exceções das funções do SUMO (`traci.vehicle.getNextTLS`, `traci.trafficlight.getProgram`, etc.). Se alguma dessas chamadas falhar (ex.: veículo desapareceu entre um tick e outro), o legado simplesmente **estoura a exceção** e interrompe a execução.

O código refatorado envolve várias dessas chamadas em blocos `try/except` e toma decisões seguras:

| Local | Comportamento refatorado |
|-------|--------------------------|
| `improve()` – `vehicle_get_next_tls(ev.veh_emergency_id)` | Se falhar, continua para o próximo veículo (`continue`). |
| `_store_green_wave()` – `getControlledLanes`, `getProgram`, `getPosition` | Se falhar, **não adiciona a alocação** (`return`). |
| `_vehicle_passed_tls_green_wave()` – `vehicle_get_next_tls` | Se falhar, assume que o veículo passou (`change_transition = True`). |
| `_green_wave_initial_transition()` / `_green_wave_final_transition()` – `getRedYellowGreenState` / `setRedYellowGreenState` | Se falhar, simplesmente retorna sem alterar nada. |
| `_remove_tls_on_green_wave()` – `trafficlight_set_program` | Se falhar, ignora e remove a alocação mesmo assim. |
| `_proportion_to_conclude_green_wave()` – `vehicle_get_position` | Se falhar, retorna `1.0` (considera veículo como tendo concluído o trajeto). |

Essas proteções **alteram o fluxo em caso de falha** e evitam crashes – o que é uma melhoria, mas não é “verbatim”.

### 2. Proteção contra divisão por zero
Na função `proportion_to_conclude_green_wave`, o legado calcula:
```python
return euclidian_distance_current / euclidian_distance_arrival
```
Se `euclidian_distance_arrival` for zero (veículo começa exatamente na posição do semáforo), o legado dispara `ZeroDivisionError`.

O refatorado trata esse caso explicitamente:
```python
if euclidian_distance_arrival == 0:
    return 1.0
```
Isso muda o resultado (de exceção para `1.0`, que significa “não pode ser preemptado”), corrigindo um bug latente.

### 3. Verificação extra do índice no loop (`key >= len(self._allocations)`)
No método `_green_wave_logic` refatorado, após `_vehicle_passed_tls_green_wave` você adicionou:
```python
if key >= len(self._allocations):
    continue
```
No legado essa checagem não existe. Na prática, nenhuma remoção ocorre antes dessa linha (as remoções só acontecem depois, no tratamento do status `RETURN_TO_PROGRAM_ORIGINAL`), então essa condição **nunca é verdadeira em operação normal**. É uma defesa inócua que não altera comportamento.

### 4. API adicional e troca de nomes
- O refatorado encapsula tudo em uma classe e expõe `active_allocations()` – isso é novo, mas não quebra o legado.
- Os nomes internos mudaram (ex.: `buffer_tls_on_green_wave` → `self._allocations`, `sumo` em vez de `traci`), mas a lógica é a mesma.

## Conclusão
**Em execução sem falhas e sem divisão por zero, os dois códigos se comportam de forma idêntica.** As diferenças estão apenas na tolerância a erros e na prevenção de crash. Se o objetivo da refatoração era manter **exatamente** o comportamento original inclusive em situações de exceção, você modificou esses pontos. Porém, as alterações são sensatas e aumentam a robustez – a maioria dos times consideraria isso uma melhoria válida, desde que documentada. Para ser totalmente fiel ao “verbatim”, você poderia remover os `try/except` e o tratamento do zero, mas provavelmente não é desejável.
