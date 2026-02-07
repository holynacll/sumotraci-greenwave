# Reinforcement Learning para Green Wave Algorithm

**Data:** 2025-12-07
**Objetivo:** Implementar RL para otimizar controle de semáforos para veículos de emergência

---

## 🎯 Visão Geral da Abordagem RL

### Por Que RL Pode Funcionar Aqui?

Apesar das desvantagens mencionadas anteriormente, RL pode trazer benefícios se implementado corretamente:

- ✅ **Aprendizado de padrões complexos**: Descobre estratégias não óbvias
- ✅ **Adaptação contínua**: Melhora com experiência
- ✅ **Balanceamento automático**: Aprende trade-offs entre objetivos
- ✅ **Generalização**: Pode lidar com cenários não vistos

### Desafios e Soluções

| Desafio | Solução Proposta |
|---------|------------------|
| Espaço de estados grande | Feature engineering + normalização |
| Esparsidade de recompensa | Reward shaping cuidadoso |
| Longo tempo de treinamento | Paralelização + warm start |
| Falta de explicabilidade | Attention mechanisms + logs detalhados |
| Instabilidade | Algoritmos estáveis (PPO/SAC) + bounded actions |

---

## 🏗️ Arquitetura RL Proposta

### Componente 1: Ambiente (SUMO Gym Environment)

```
┌─────────────────────────────────────────────────────┐
│            GreenWaveRLEnvironment                    │
│                  (Gymnasium)                         │
├─────────────────────────────────────────────────────┤
│                                                      │
│  State Space:                                        │
│  ┌────────────────────────────────────────┐        │
│  │ - ev_distance_to_tls                   │        │
│  │ - ev_speed, ev_acceleration            │        │
│  │ - deadline_urgency [0-1]               │        │
│  │ - traffic_density [0-1]                │        │
│  │ - queue_length (normalized)            │        │
│  │ - current_tls_phase                    │        │
│  │ - time_in_current_phase                │        │
│  │ - num_vehicles_waiting                 │        │
│  └────────────────────────────────────────┘        │
│                                                      │
│  Action Space:                                       │
│  ┌────────────────────────────────────────┐        │
│  │ Discrete(5) ou Continuous(2):          │        │
│  │                                         │        │
│  │ Option A - Discrete:                    │        │
│  │   0: Keep current phase                │        │
│  │   1: Transition to green (fast)        │        │
│  │   2: Transition to green (normal)      │        │
│  │   3: Extend green (short)              │        │
│  │   4: Extend green (long)               │        │
│  │                                         │        │
│  │ Option B - Continuous:                  │        │
│  │   [transition_time, green_duration]    │        │
│  │   bounded: [4-12s, 15-45s]             │        │
│  └────────────────────────────────────────┘        │
│                                                      │
│  Reward Function:                                    │
│  ┌────────────────────────────────────────┐        │
│  │ r = -w1*ev_time                        │        │
│  │     -w2*traffic_delay                  │        │
│  │     -w3*num_stops                      │        │
│  │     +w4*deadline_met                   │        │
│  │     -w5*unsafe_transitions             │        │
│  └────────────────────────────────────────┘        │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### Componente 2: Agente RL

Vou implementar **duas versões**:

1. **DQN (Deep Q-Network)**: Para ações discretas, mais simples
2. **PPO (Proximal Policy Optimization)**: Para ações contínuas, mais estável

---

## 💻 Implementação

### Estrutura de Arquivos

```
src/
├── rl_green_wave/
│   ├── __init__.py
│   ├── environment.py              # Gymnasium environment
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── dqn_agent.py           # DQN implementation
│   │   ├── ppo_agent.py           # PPO implementation
│   │   └── networks.py            # Neural networks
│   ├── training/
│   │   ├── __init__.py
│   │   ├── trainer.py             # Training loop
│   │   ├── replay_buffer.py       # Experience replay
│   │   └── callbacks.py           # Logging callbacks
│   ├── evaluation/
│   │   ├── __init__.py
│   │   ├── evaluator.py           # Evaluation metrics
│   │   └── visualizer.py          # Visualization tools
│   └── integration/
│       ├── __init__.py
│       └── rl_controller.py       # Integration with current system
└── experiments/
    ├── train_rl_agent.py          # Training script
    ├── evaluate_rl_agent.py       # Evaluation script
    └── compare_algorithms.py      # Benchmark: RL vs Baseline
```

---

## 📝 Código de Implementação

Vou criar os arquivos principais agora.

### Requisitos

```
gymnasium>=0.29.0
stable-baselines3>=2.2.0
torch>=2.0.0
numpy>=1.24.0
pandas>=2.0.0
matplotlib>=3.7.0
tensorboard>=2.15.0
```

---

## 🔍 Decisões de Design

### 1. Espaço de Estados (State Space)

**Normalização é crítica:**
- Distância: [0-500m] → [0-1]
- Velocidade: [0-20m/s] → [0-1]
- Urgência: já em [0-1]
- Densidade: já em [0-1]

**Features adicionais:**
- Tempo relativo até deadline
- Histórico de fases recentes (últimas 3)
- Taxa de chegada de veículos

### 2. Espaço de Ações (Action Space)

**Opção A - Discreto (recomendado para começar):**
```python
actions = {
    0: "MAINTAIN",           # Mantém fase atual
    1: "QUICK_GREEN",        # Verde rápido (4s transition, 20s green)
    2: "NORMAL_GREEN",       # Verde normal (8s transition, 30s green)
    3: "EXTENDED_GREEN",     # Verde longo (8s transition, 40s green)
    4: "EMERGENCY_PRIORITY"  # Prioridade máxima (4s transition, 45s green)
}
```

**Opção B - Contínuo (mais flexível, mas mais difícil de treinar):**
```python
action = [transition_time, green_duration]
# Bounded: [4-12], [15-45]
```

### 3. Função de Recompensa (Reward Function)

**Versão 1 - Simples:**
```python
reward = -ev_travel_time  # Apenas minimiza tempo do VE
```

**Versão 2 - Balanceada (recomendada):**
```python
reward = (
    -0.5 * ev_travel_time_normalized      # Tempo do VE
    -0.2 * traffic_delay_normalized       # Impacto no tráfego
    -0.1 * num_stops                      # Número de paradas
    +1.0 if deadline_met else -2.0        # Bônus/penalidade deadline
    -0.2 * unsafe_penalty                 # Penalidade transições perigosas
)
```

**Versão 3 - Shaped (para convergência mais rápida):**
```python
# Recompensas intermediárias
reward = 0

# Reward shaping progressivo
if ev_approaching_tls:
    reward += 0.1 * (1 - distance_normalized)  # Recompensa aproximação

if tls_green_when_ev_arrives:
    reward += 0.5  # Bônus coordenação

if ev_passes_without_stopping:
    reward += 1.0  # Grande bônus

if deadline_met:
    reward += 2.0
else:
    reward -= 3.0

# Penalidades
reward -= 0.3 * traffic_delay_normalized
reward -= 0.1 * num_stops
```

### 4. Algoritmo RL

**DQN (Deep Q-Network):**
- ✅ Mais simples de implementar
- ✅ Funciona bem com ações discretas
- ✅ Menos hyperparameters
- ⚠️ Pode ser instável em alguns casos

**PPO (Proximal Policy Optimization):**
- ✅ Muito estável
- ✅ Funciona com ações contínuas
- ✅ State-of-the-art para problemas de controle
- ⚠️ Mais complexo

**Recomendação inicial: DQN com ações discretas**

---

## 🎓 Estratégia de Treinamento

### Fase 1: Curriculum Learning (Semanas 1-2)

Começar com cenários simples e aumentar complexidade gradualmente:

```python
# Nível 1: Single EV, baixo tráfego, deadline folgado
curriculum_stage_1 = {
    'num_evs': 1,
    'traffic_density': 0.2,
    'deadline_pressure': 0.3,
    'num_tls_on_route': 2
}

# Nível 2: Single EV, tráfego médio, deadline médio
curriculum_stage_2 = {
    'num_evs': 1,
    'traffic_density': 0.5,
    'deadline_pressure': 0.6,
    'num_tls_on_route': 3
}

# Nível 3: Múltiplos EVs, tráfego alto, deadlines variados
curriculum_stage_3 = {
    'num_evs': 2,
    'traffic_density': 0.7,
    'deadline_pressure': 0.8,
    'num_tls_on_route': 4
}
```

### Fase 2: Warm Start (Opcional)

**Imitation Learning**: Treinar primeiro para imitar o sistema atual:

```python
# Coletar demonstrações do sistema atual
demonstrations = collect_expert_trajectories(
    num_episodes=100,
    algorithm='current_green_wave'
)

# Pre-treinar agente com Behavioral Cloning
agent.pretrain_with_imitation(demonstrations)

# Depois, fazer fine-tuning com RL
agent.train_with_rl()
```

### Fase 3: Exploration Strategy

```python
# Epsilon-greedy decay
epsilon_start = 1.0
epsilon_end = 0.05
epsilon_decay = 0.995

# OU: Boltzmann exploration (para ações contínuas)
temperature_start = 1.0
temperature_end = 0.1
temperature_decay = 0.99
```

### Fase 4: Hyperparameters

```python
hyperparameters = {
    # Network
    'hidden_layers': [128, 128, 64],
    'activation': 'relu',
    'learning_rate': 3e-4,

    # Training
    'batch_size': 64,
    'buffer_size': 100000,
    'gamma': 0.99,  # discount factor
    'tau': 0.005,   # soft update

    # DQN specific
    'target_update_freq': 1000,
    'gradient_steps': 1,

    # PPO specific
    'n_steps': 2048,
    'n_epochs': 10,
    'clip_range': 0.2,
}
```

---

## 📊 Métricas de Avaliação

### Durante o Treinamento

```python
metrics = {
    # Performance
    'mean_episode_reward': [],
    'mean_ev_travel_time': [],
    'mean_traffic_delay': [],
    'deadline_success_rate': [],

    # Learning
    'loss': [],
    'q_values': [],
    'entropy': [],  # Para PPO

    # Exploration
    'epsilon': [],
    'actions_distribution': [],
}
```

### Após o Treinamento

```python
evaluation_metrics = {
    # Comparação com baseline
    'improvement_ev_time': [],
    'improvement_traffic_delay': [],
    'deadline_success_rate_delta': [],

    # Robustez
    'performance_variance': [],
    'failure_rate': [],

    # Generalização
    'performance_unseen_scenarios': [],
}
```

---

## 🛡️ Safety Constraints

**Crítico: RL pode tomar ações perigosas. Implementar validação:**

```python
class SafetyValidator:
    """Valida ações do agente RL antes de aplicar"""

    def validate_action(self, state, action):
        # 1. Tempo de transição mínimo
        if action.transition_time < 4.0:
            action.transition_time = 4.0

        # 2. Duração mínima de verde
        if action.green_duration < 15.0:
            action.green_duration = 15.0

        # 3. Não mudar fase muito rapidamente
        if state.time_in_phase < 3.0:
            return None  # Reject action

        # 4. Considerar tráfego conflitante
        if state.conflicting_traffic_high and action.transition_time < 6.0:
            action.transition_time = 6.0

        return action
```

---

## 🔄 Integração com Sistema Atual

```python
class HybridRLController:
    """Combina RL com sistema atual para segurança"""

    def __init__(self):
        self.rl_agent = trained_rl_agent
        self.baseline = current_green_wave_logic
        self.safety_validator = SafetyValidator()
        self.confidence_threshold = 0.7

    def get_action(self, state):
        # RL propõe ação
        rl_action, confidence = self.rl_agent.predict(state)

        # Valida segurança
        rl_action = self.safety_validator.validate_action(state, rl_action)

        # Se RL não confiante ou ação inválida, usa baseline
        if confidence < self.confidence_threshold or rl_action is None:
            return self.baseline.get_action(state)

        return rl_action
```

---

## 📈 Experimento Proposto

### Setup

```python
experiment_config = {
    'name': 'rl_vs_baseline_green_wave',
    'algorithms': ['baseline', 'dqn', 'ppo'],
    'num_episodes_per_algo': 100,
    'scenarios': [
        'low_traffic_low_urgency',
        'medium_traffic_medium_urgency',
        'high_traffic_high_urgency',
        'multiple_evs',
        'mixed_conditions'
    ],
    'metrics': [
        'ev_travel_time',
        'traffic_delay',
        'deadline_success_rate',
        'num_stops',
        'emissions'
    ]
}
```

### Análise Estatística

```python
# Teste de significância
from scipy.stats import ttest_ind

results_baseline = evaluate(baseline_controller, scenarios)
results_rl = evaluate(rl_controller, scenarios)

t_stat, p_value = ttest_ind(
    results_baseline['ev_travel_time'],
    results_rl['ev_travel_time']
)

if p_value < 0.05:
    print(f"RL is significantly better (p={p_value:.4f})")
```

---

## ⚙️ Próximos Passos de Implementação

Vou criar os arquivos de código agora. Quer que eu:

1. ✅ Implemente o ambiente Gymnasium
2. ✅ Implemente o agente DQN
3. ✅ Crie script de treinamento
4. ✅ Crie integração com sistema atual
5. ✅ Adicione notebooks de análise

Continuo com a implementação?
