# Abordagens para Melhoria do Green Wave Algorithm (GWA)

**Data:** 2025-12-07
**Objetivo:** Documentar abordagens alternativas para otimizar o Traffic Signal Control (TSC) no contexto de veículos de emergência, mantendo **eficiência** e **explicabilidade**.

---

## 📋 Contexto do Problema

### Desafios do TSC (Traffic Signal Control)

O controle ótimo de sinais de tráfego busca tempos de sinalização eficazes para otimizar o fluxo do trânsito, necessitando de ajustes em tempo real para:

- ✅ Reduzir congestionamentos
- ✅ Minimizar tempo de espera
- ✅ Priorizar veículos de emergência (VE)
- ✅ Minimizar impacto no tráfego geral
- ✅ Reduzir emissões

### Desafios Específicos

- **Layouts complexos**: Múltiplos semáforos interdependentes
- **Fluxos flutuantes**: Variação temporal e espacial de tráfego
- **Múltiplos objetivos**: Trade-offs entre eficiência e segurança
- **Incerteza**: Comportamento imprevisível de veículos

### Sistema Atual

O sistema implementa:
- **EDF (Earliest Deadline First)**: Priorização baseada em deadline
- **Green Wave determinístico**: Máquina de estados com transições fixas
- **Parâmetros estáticos**: Tempos de transição e distâncias pré-definidos

**Pontos Fortes:**
- Previsível e confiável
- Fácil de auditar
- Baseado em física do problema
- Funciona bem em cenários simulados

**Limitações:**
- Não se adapta dinamicamente ao estado do tráfego
- Tempos de transição fixos podem não ser ótimos
- Não considera múltiplos VEs simultâneos de forma otimizada
- Não aprende com experiências passadas

---

## 🎯 Arquitetura Proposta: Adaptive Green Wave Controller (AGWC)

### Princípios de Design

1. **Explicabilidade First**: Toda decisão deve ser auditável e compreensível
2. **Eficiência Adaptativa**: Ajustes em tempo real baseados em contexto
3. **Modularidade**: Componentes independentes e testáveis
4. **Segurança**: Validações e fallbacks para situações críticas
5. **Compatibilidade**: Coexistir com sistema atual para comparação

### Componentes Principais

```
┌─────────────────────────────────────────────────────────┐
│         Adaptive Green Wave Controller (AGWC)           │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────┐  ┌──────────────────┐              │
│  │  EDF Scheduler │──│ Prediction Engine│              │
│  │   (Deadline)   │  │  (Trajectory)    │              │
│  └────────────────┘  └──────────────────┘              │
│           │                    │                        │
│           ▼                    ▼                        │
│  ┌─────────────────────────────────────┐               │
│  │   Decision Engine                   │               │
│  │   (Fuzzy / DT / MPC)                │               │
│  └─────────────────────────────────────┘               │
│           │                                             │
│           ▼                                             │
│  ┌─────────────────────────────────────┐               │
│  │  Phase Transition Optimizer         │               │
│  │  (Adaptive Timing)                  │               │
│  └─────────────────────────────────────┘               │
│           │                                             │
│           ▼                                             │
│  ┌─────────────────────────────────────┐               │
│  │  Traffic Light Controller           │               │
│  │  (SUMO TraCI Interface)             │               │
│  └─────────────────────────────────────┘               │
│                                                          │
│  ┌─────────────────────────────────────┐               │
│  │  Telemetry & Explainability Logger  │               │
│  └─────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────┘
```

---

## 🔬 Abordagem 1: Fuzzy Logic System (FLS)

### Visão Geral

Sistema baseado em **lógica difusa (fuzzy)** que modela incertezas e permite raciocínio baseado em regras linguísticas naturais.

### Por Que Fuzzy Logic?

- ✅ **Alta explicabilidade**: Regras em linguagem natural
- ✅ **Modelagem de incerteza**: Lida bem com imprecisão
- ✅ **Experiência humana**: Incorpora conhecimento de especialistas
- ✅ **Não requer treinamento**: Baseado em regras definidas
- ⚠️ **Tunning manual**: Requer ajuste de funções de pertinência

### Arquitetura Fuzzy

```
Input Variables (Fuzzification)
    ↓
┌─────────────────────────────┐
│ traffic_density             │ → {LOW, MEDIUM, HIGH, VERY_HIGH}
│ deadline_urgency            │ → {LOW, MEDIUM, HIGH, CRITICAL}
│ queue_length                │ → {SHORT, MEDIUM, LONG}
│ ev_distance_to_tls          │ → {FAR, MEDIUM, NEAR, VERY_NEAR}
└─────────────────────────────┘
    ↓
Rule Base (Inference)
    ↓
┌─────────────────────────────────────────────────────────┐
│ SE traffic_density é HIGH E deadline_urgency é CRITICAL │
│ ENTÃO transition_time é VERY_SHORT                      │
│                                                          │
│ SE ev_distance_to_tls é VERY_NEAR E queue_length é LONG │
│ ENTÃO green_duration é LONG                             │
└─────────────────────────────────────────────────────────┘
    ↓
Output Variables (Defuzzification)
    ↓
┌─────────────────────────────┐
│ transition_time             │ → [4.0 - 12.0] seconds
│ green_duration              │ → [15.0 - 45.0] seconds
│ priority_weight             │ → [0.0 - 1.0]
└─────────────────────────────┘
```

### Exemplo de Regras Fuzzy

```python
# Regras de alta prioridade
SE deadline_urgency é CRITICAL E ev_distance é VERY_NEAR
   ENTÃO transition_time é VERY_SHORT (4-5s)
         green_duration é LONG (40-45s)

# Regras balanceadas
SE deadline_urgency é MEDIUM E traffic_density é HIGH
   ENTÃO transition_time é SHORT (6-7s)
         green_duration é MEDIUM (25-30s)

# Regras de proteção ao tráfego
SE traffic_density é VERY_HIGH E queue_length é LONG
   ENTÃO green_duration é LONG (35-45s)
         (prioriza dispersão da fila)
```

### Vantagens

- ✅ **Explicabilidade total**: Cada decisão rastreável até regras específicas
- ✅ **Flexibilidade**: Fácil adicionar/ajustar regras
- ✅ **Sem dados de treinamento**: Usa conhecimento especialista
- ✅ **Adaptação gradual**: Suaviza transições entre estados
- ✅ **Robustez a ruído**: Lógica fuzzy lida bem com imprecisão

### Desvantagens

- ⚠️ **Ajuste manual**: Funções de pertinência requerem tunning
- ⚠️ **Escalabilidade limitada**: Muitas variáveis = muitas regras
- ⚠️ **Não aprende**: Não melhora automaticamente

### Bibliotecas e Ferramentas

- **scikit-fuzzy**: https://github.com/scikit-fuzzy/scikit-fuzzy
- **simpful**: https://github.com/aresio/simpful (alternativa mais simples)

---

## 🌳 Abordagem 2: Decision Tree + Optimization

### Visão Geral

Sistema híbrido que combina **árvores de decisão** (treinadas em dados simulados) com **otimização local** para refinar decisões.

### Por Que Decision Trees?

- ✅ **Visualizável**: Árvore pode ser plotada graficamente
- ✅ **Explicável**: Caminho de decisão é claro
- ✅ **Aprende com dados**: Captura padrões históricos
- ✅ **Rápido**: Inferência em tempo real
- ⚠️ **Requer dados**: Precisa de simulações para treinar

### Arquitetura Decision Tree

```
Historical Data Collection
    ↓
┌─────────────────────────────────────────┐
│ Simulate multiple scenarios             │
│ - Different traffic densities           │
│ - Different EV urgencies                │
│ - Different time constraints            │
│                                          │
│ Collect: (state, action, reward)        │
└─────────────────────────────────────────┘
    ↓
Decision Tree Training
    ↓
┌─────────────────────────────────────────┐
│ Features:                                │
│ - traffic_density                        │
│ - deadline_urgency                       │
│ - ev_distance                            │
│ - queue_length                           │
│ - time_of_day                            │
│                                          │
│ Target:                                  │
│ - optimal_transition_time                │
│ - optimal_green_duration                 │
└─────────────────────────────────────────┘
    ↓
Local Optimization (Hill Climbing)
    ↓
┌─────────────────────────────────────────┐
│ Refine tree prediction:                 │
│ - Check neighbor solutions               │
│ - Evaluate multi-objective function      │
│ - Select best refined solution           │
└─────────────────────────────────────────┘
```

### Processo de Coleta de Dados

```python
# Pseudocódigo para coleta
for transition_time in [4, 6, 8, 10, 12]:
    for green_duration in [15, 25, 35, 45]:
        # Executa simulação com parâmetros fixos
        metrics = run_simulation(transition_time, green_duration)

        # Armazena: estado, ação, resultado
        data.append({
            'traffic_density': metrics.density,
            'deadline_urgency': metrics.urgency,
            'ev_distance': metrics.distance,
            'queue_length': metrics.queue,
            'transition_time': transition_time,
            'green_duration': green_duration,
            'ev_arrival_time': metrics.ev_time,  # target
            'traffic_delay': metrics.delay        # target
        })
```

### Vantagens

- ✅ **Aprende com dados**: Captura padrões empíricos
- ✅ **Explicável**: Caminho visualizável
- ✅ **Otimização adicional**: Hill Climbing refina solução
- ✅ **Balanceamento automático**: Aprende trade-offs
- ✅ **Visualizável**: Árvore pode ser plotada

### Desvantagens

- ⚠️ **Requer dados**: Muitas simulações necessárias
- ⚠️ **Overfitting**: Pode se ajustar demais ao treino
- ⚠️ **Estacionaridade**: Assume padrões estáveis

### Bibliotecas e Ferramentas

- **scikit-learn**: DecisionTreeRegressor, plot_tree
- **XGBoost/LightGBM**: Versões mais robustas
- **SHAP**: Explicabilidade avançada

---

## 🎮 Abordagem 3: Model Predictive Control (MPC)

### Visão Geral

Sistema de **controle preditivo** que otimiza sequência de ações futuras considerando modelo dinâmico e restrições.

### Por Que MPC?

- ✅ **Otimização com horizonte**: Planeja múltiplos passos à frente
- ✅ **Restrições explícitas**: Limites de segurança garantidos
- ✅ **Modelo físico**: Usa equações de movimento
- ✅ **Coordenação**: Otimiza múltiplos semáforos simultaneamente
- ⚠️ **Custo computacional**: Requer solver de otimização

### Arquitetura MPC

```
Current State
    ↓
┌─────────────────────────────────────────┐
│ State Estimation                         │
│ - EV position, speed, acceleration       │
│ - Traffic density per lane               │
│ - Current TLS states                     │
└─────────────────────────────────────────┘
    ↓
Prediction Horizon (N steps ahead)
    ↓
┌─────────────────────────────────────────┐
│ Dynamic Model                            │
│                                          │
│ x(t+1) = f(x(t), u(t))                  │
│                                          │
│ x = [ev_position, ev_speed, ...]        │
│ u = [tls_state_1, tls_state_2, ...]    │
└─────────────────────────────────────────┘
    ↓
Optimization Problem
    ↓
┌─────────────────────────────────────────┐
│ Minimize:                                │
│   J = Σ (w1*ev_delay + w2*traffic_delay) │
│                                          │
│ Subject to:                              │
│   - tls_state ∈ {red, yellow, green}    │
│   - transition_time >= 4s                │
│   - green_duration >= 15s                │
│   - ev_speed <= speed_limit              │
└─────────────────────────────────────────┘
    ↓
Optimal Control Sequence
    ↓
Apply First Control (Receding Horizon)
```

### Formulação Matemática Simplificada

```
Minimizar: J = Σ(t=0 to N) [w1 * delay_ev(t) + w2 * delay_traffic(t)]

Sujeito a:
  - pos_ev(t+1) = pos_ev(t) + vel_ev(t) * dt
  - vel_ev(t+1) = f(vel_ev(t), tls_state(t))
  - tls_green_duration(i) >= 15s
  - tls_transition_time(i) >= 4s
  - Coordenação: tls(i+1) abre quando EV chega
```

### Vantagens

- ✅ **Otimização global**: Considera múltiplos semáforos
- ✅ **Restrições explícitas**: Segurança matemática
- ✅ **Coordenação**: Verdadeiro "green wave"
- ✅ **Adaptação**: Replaneja a cada passo
- ✅ **Previsibilidade**: Baseado em física

### Desvantagens

- ⚠️ **Complexidade computacional**: Requer solver
- ⚠️ **Modelo simplificado**: Tráfego real é muito complexo
- ⚠️ **Tempo de computação**: Pode ser lento
- ⚠️ **Fallback necessário**: Precisa solução alternativa

### Bibliotecas e Ferramentas

- **CVXPY**: https://www.cvxpy.org/
- **do-mpc**: https://www.do-mpc.com/
- **CasADi**: https://web.casadi.org/

---

## 📊 Comparação das Abordagens

| Critério | Fuzzy Logic | Decision Tree | MPC |
|----------|-------------|---------------|-----|
| **Explicabilidade** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Eficiência Computacional** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| **Adaptabilidade** | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Coordenação Multi-TLS** | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Facilidade Implementação** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **Robustez** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **Manutenção** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| **Requer Dados** | ❌ Não | ✅ Sim | ❌ Não |
| **Aprende** | ❌ Não | ✅ Sim | ❌ Não |

---

## 🚀 Recomendação de Implementação

### Abordagem Híbrida em Fases

#### **Fase 1: Fuzzy Logic (Curto Prazo - 2-4 semanas)**
**Objetivo:** Validar conceito de controle adaptativo

**Tarefas:**
1. Implementar controlador fuzzy básico (4-5 variáveis)
2. Integrar com sistema atual (modo A/B test)
3. Implementar telemetria completa
4. Comparar métricas: Fuzzy vs Baseline

**Entregáveis:**
- Classe `FuzzyGreenWaveController`
- Relatório de comparação de desempenho
- Análise de explicabilidade

---

#### **Fase 2: Decision Tree (Médio Prazo - 1-2 meses)**
**Objetivo:** Aprender padrões ótimos dos dados

**Tarefas:**
1. Coletar dados de simulações (Fuzzy + Baseline)
2. Treinar Decision Tree multi-output
3. Implementar otimização local (Hill Climbing)
4. Comparar: Fuzzy vs Tree vs Baseline

**Entregáveis:**
- Dataset de treinamento (>1000 amostras)
- Classe `DecisionTreeGreenWaveController`
- Visualizações de árvores de decisão
- Análise de feature importance

---

#### **Fase 3: MPC (Longo Prazo - 3-6 meses)**
**Objetivo:** Coordenação global de semáforos

**Tarefas:**
1. Implementar MPC simplificado (horizonte curto)
2. Usar Fuzzy/Tree como fallback
3. Avaliar benefício da coordenação multi-TLS
4. Análise de custo-benefício computacional

**Entregáveis:**
- Classe `MPCGreenWaveController`
- Comparação: MPC vs Fuzzy vs Tree vs Baseline
- Análise de overhead computacional

---

### Sistema Híbrido Final

```python
class HybridGreenWaveController:
    """Sistema híbrido que seleciona melhor abordagem por contexto"""

    def __init__(self):
        self.fuzzy = FuzzyGreenWaveController()
        self.tree = DecisionTreeGreenWaveController()
        self.mpc = MPCGreenWaveController()
        self.mode = 'auto'

    def optimize(self, context):
        """Seleciona abordagem baseado em contexto"""

        if context.num_tls_ahead >= 3 and context.computational_budget_ok:
            # MPC para coordenação global
            return self.mpc.optimize(context)

        elif self.tree.is_trained and context.similar_to_training:
            # Decision Tree quando dados são representativos
            return self.tree.predict(context)

        else:
            # Fuzzy como baseline robusto
            return self.fuzzy.compute(context)
```

---

## 📝 Próximos Passos Práticos

### Imediato (Esta Semana)

1. **Corrigir bug identificado** em `optimization_green_wave.py:201`
   ```python
   # Linha 201: trocar == por =
   settings.buffer_tls_on_green_wave[key]['status'] = 'FINAL_TRANSITION'
   ```

2. **Implementar telemetria básica** no sistema atual
   - Métricas: tempo_ev, delay_trafego, num_veiculos_impactados
   - Exportar para CSV a cada simulação
   - Estabelecer baseline estatístico

### Curto Prazo (Próximas 2-4 Semanas)

3. **Prototipar Fuzzy Logic Controller**
   - Instalar `scikit-fuzzy`
   - Implementar versão mínima (3-4 inputs, 2 outputs)
   - Integrar com modo A/B test
   - Coletar métricas comparativas

4. **Análise de dados existentes**
   - Revisar notebooks de resultados
   - Identificar padrões nos dados históricos
   - Validar hipóteses sobre parâmetros ótimos

### Médio Prazo (1-3 Meses)

5. **Coletar dados para Decision Tree**
   - Executar grid search sistemático de parâmetros
   - Coletar >1000 amostras variadas
   - Preparar dataset para treinamento

6. **Implementar e treinar Decision Tree**
   - Treinar modelo multi-output
   - Validar com cross-validation
   - Comparar com Fuzzy e Baseline

### Longo Prazo (3-6 Meses)

7. **Explorar MPC para coordenação**
   - Protótipo simplificado
   - Avaliar viabilidade computacional
   - Comparar benefício vs custo

8. **Refatoração arquitetural** (conforme `improvements.md`)
   - Separar classes: Controller, Incident Manager, Infrastructure
   - Melhorar documentação
   - Aplicar boas práticas Python

---

## 💡 Considerações Finais

### Por Que NÃO Reinforcement Learning?

Todas as três abordagens propostas são **superiores a RL** para este problema:

1. ✅ **Explicabilidade garantida**: Decisões auditáveis
2. ✅ **Convergência rápida**: Não requer milhões de episódios
3. ✅ **Estabilidade**: Comportamento previsível
4. ✅ **Debug facilitado**: Problemas identificáveis
5. ✅ **Certificação**: Validação para sistemas críticos

### Critérios de Escolha

**Use Fuzzy Logic se:**
- Explicabilidade é mandatória
- Dados para treinamento são limitados
- Conhecimento especialista está disponível
- Comportamento previsível é crítico

**Use Decision Tree se:**
- Há recursos para coletar dados
- Padrões são complexos para regras manuais
- Quer balancear múltiplos objetivos empiricamente
- Explicabilidade parcial é aceitável

**Use MPC se:**
- Coordenação multi-TLS é essencial
- Restrições de segurança são complexas
- Há recursos computacionais disponíveis
- Modelo físico é bem conhecido

### Recomendação Final

**Comece com Fuzzy Logic** para:
- Validar rapidamente o conceito adaptativo
- Estabelecer baseline de explicabilidade
- Ganhar intuição sobre o problema

**Evolua para Decision Tree** se:
- Fuzzy mostrar benefícios claros
- Houver necessidade de aprender padrões complexos
- Recursos para coleta de dados estiverem disponíveis

**Considere MPC** apenas se:
- Coordenação multi-TLS mostrar grande potencial
- Overhead computacional for aceitável
- Outras abordagens atingirem teto de desempenho

---

## 📚 Referências e Recursos

### Papers Relevantes

1. **Fuzzy Logic for Traffic Control**
   - "Fuzzy Logic Controllers for Traffic Light Control" (IEEE)
   - "Adaptive Traffic Signal Control Using Fuzzy Logic"

2. **Decision Trees for TSC**
   - "Learning Traffic Signal Control Policies via Decision Trees"
   - "Explainable AI for Intelligent Transportation Systems"

3. **Model Predictive Control**
   - "Coordinated Traffic Signal Control Using MPC"
   - "Real-time MPC for Urban Traffic Networks"

### Bibliotecas Python

- **Fuzzy Logic**: `scikit-fuzzy`, `simpful`
- **Decision Trees**: `scikit-learn`, `xgboost`, `lightgbm`
- **MPC**: `cvxpy`, `do-mpc`, `casadi`
- **Explicabilidade**: `shap`, `lime`
- **Visualização**: `matplotlib`, `graphviz`, `plotly`

### Tutoriais e Cursos

- Fuzzy Logic: https://pythonhosted.org/scikit-fuzzy/
- Decision Trees: https://scikit-learn.org/stable/modules/tree.html
- MPC: https://www.do-mpc.com/en/latest/getting_started.html

---

## 🔧 Estrutura de Código Sugerida

```
src/
├── optimization_green_wave.py          # Sistema atual
├── adaptive_controllers/
│   ├── __init__.py
│   ├── base_controller.py             # Interface abstrata
│   ├── fuzzy_controller.py            # Fuzzy Logic
│   ├── tree_controller.py             # Decision Tree
│   ├── mpc_controller.py              # MPC
│   └── hybrid_controller.py           # Seletor automático
├── telemetry/
│   ├── __init__.py
│   ├── metrics_collector.py           # Coleta métricas
│   ├── explainability_logger.py       # Logs de decisões
│   └── performance_analyzer.py        # Análise comparativa
├── utils/
│   ├── traffic_state_estimator.py     # Estimação de estado
│   ├── trajectory_predictor.py        # Predição de trajetória
│   └── safety_validator.py            # Validação de segurança
└── experiments/
    ├── run_comparison.py               # A/B test
    ├── collect_training_data.py        # Coleta para DT
    └── analyze_results.py              # Análise estatística
```

---

**Última atualização:** 2025-12-07
**Autor:** Documentação gerada para projeto SUMO TraCI Green Wave
**Status:** Proposta para implementação futura
