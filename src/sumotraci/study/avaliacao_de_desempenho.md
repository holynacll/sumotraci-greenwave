# Processo Experimental Sistemático
  - ## Problema: (introdução)
    - Os veículos de emergência precisam de um caminho livre para chegarem rapidamente ao seu destino. Embora possam passar por sinais vermelhos, o alto volume de tráfego e os semáforos com ciclos fixos podem criar congestionamentos que bloqueiam o caminho. Esses veículos normais se tornam obstáculos, prejudicando a duração da viagem dos veículos de emergência.
  - ## Pergunta: (introdução)
    1. Como reduzir o tempo de viagem dos veículos de emergência?
    2. É possível modificar o comportamento dos semáforos para que abram à medida que os veículos de emergência se aproximem, aumentando a vazão nas próximas faixas e diminuindo a presença de veículos normais que seriam obstáculos?
    3. Podemos avaliar a influência no trânsito e nos serviços prestados pelos veículos de emergência modificando o controle de sinais de trânsito com o Green Wave?
    4. Dado que o trânsito possui inúmeros cenários possíveis com vários fatores influenciando a qualidade, segurança e saúde do tráfego, é possível formular um método replicável e otimizado para avaliar essas possibilidades?
    5. No contexto de emergências médicas, onde o "golden time" marca um prazo limite para atendimento bem-sucedido, é possível formular um método que avalie a priorização de diferentes acidentes ocorrendo simultaneamente?
  - ## Objetivo (conclusão da introdução)
    1. Reduzir o tempo de duração das viagens dos veículos de emergência.
    2. Elaborar cenário de atendimento de veículos de emergência à acidentes de trânsito com deadline diverso;
    3. Elaborar algoritmo Green Wave integrado ao escalonamento dinâmico de veículos de emergência baseado na gravidade do acidente.
    0. Planejar e executar experimentos para avaliar a influência do Green Wave em comparação com o controle padrão de semáforos. (metodologia)
    0. Utilizar SUMO/TraCI para simular cenários de acidentes com diferentes deadlines e despachar veículos de emergência para atendê-los. (meotodologia)
  - ## Métricas selecionadas: (EXPERIMENTAL RESULTS)
    1. Duração da viagem (segundos)
    2. Tempo perdido na viagem (segundos) - soma do tempo de paradas (vehicle_speed == 0 por mais de 0.01 seg)
    3. Quantidade de atendimentos bem-sucedido e não sucedidos conforme o deadline (inteiro)
  - ## Parâmetros identificados: (EXPERIMENTAL RESULTS)
    1. Número de veículos
    2. Frequência de acidentes por minuto
    3. Tempo de atraso no despacho do veículo de emergência
    4. Modelo de seguimento de carro
    5. Algoritmo de controle dos semáforos (com green wave com EDF by Deadline e sem green wave)
    6. Número de vias acidentadas
    7. Distância do veículo de emergência aos semáforos para acionamento do Green Wave
    8. Tempo de bloqueio inicial de criação de acidentes
    9. Quantidade máxima de acidentes numa mesma via
    10. Tempo de simulação
    11. Comprimento da via
    12. Tempo de transição de fases do Green Wave
    13. Distância mínima do veículo de emergência ao veículo acidentado para resolução do acidente na via
    14. Gravidade do Acidente
    15. Golden Time conforme Gravidade do Acidente
    16. Velocidade permitida da via
    17. Velocidade da via acidentada
  - ## Parâmetros Selecionados (Fatores): (EXPERIMENTAL RESULTS)
    - Frequência de acidentes por minuto
    - Tempo de atraso no despacho de veículo de emergência
    - Modelo de seguimento de carro
    - Algoritmo de controle dos semáforos (com green wave com EDF by Deadline e sem green wave)
  - ## Técnica adotada: (APPROACH PROPOSED)
    0. Congestionamento
      - O congestionamento é um sintoma crônico presente nos grandes fluxos de tráfegos urbanos no mundo, que traz uma serie de impactos negativos que pertubam a eficiência e saúde ao meio que o tangencia. Dentre os impactos causados, a piora de serviços de atendimento que precisam passar pelos congestionamentos, a exemplo dos acidentes a serem socorridos, além de aumentar o indice de causa do mesmo, onde é preciso que véiculos de emergência, e quem os pilota, tenham que lidar com uma viagem de maior risco, se não tivesse congestionamento, até o local de socorro sendo solicitado. [5], [11], [12]

    0. Metodologia
      - Foi necessário construir um cenário de trânsito que embarcasse um grande fluxo de tráfego e apresentasse congestionamentos, de modo a ser percebido o desempenho do controle de semáforos por ciclo fixo temporizado cair. Cenários que não tem presença de congestionamentos não mostram um desempenho grande ineficiência nas viagens dos veículos de emergência, desde os que mesmos possuem direitos especiais no trânsito, no momento de atuação do serviço. 
      O dispositivo BlueLight.Device, objeto do SUMO, pode ser incorporado em um veículo de emergência para obter os privilégios especiais de trânsito a qualquer tempo. Alguns do privilégios adotados são:
        - 
    0. Ambulance Profile:
      - Para poder simular o perfil de condução das ambulâncias, deve ser garantido que elas possam ultrapassar o tráfego de forma realista, formando faixas de emergência. Na simulação com utilização do modelo de subfaixa, outros veículos formam vias de emergência, mas a ambulância não os utilizou inicialmente. Isso não só significava que as ambulâncias não tinham vantagem de tempo sobre os usuários normais da estrada, mas também 0,00,51,01,52,02,50600120018002400peso de tempo na contagem média do dia em hhmm60
    1. Cenário:
      - Uso do simulador de trânsito SUMO (Simulation of Urban MObility) com a API TraCI integrada ao Python;
      - Cenário de trânsito baseado no modelo de Manhattan, com 5 vias horizontais e verticais que se cruzam formando uma Grid, e cada via com 3 faixas;
      - Cada cruzamento possui um semáforo que controla as vias que o intersecta;
      - Veículos trafegam com viagens aleatórias.
      - Uso do SUMO (Simulation of Urban MObility) em com a API TraCI integrada ao Python.
      - Cenario de trânsito baseado no modelo de Manhattan, gerado pela ferramenta netgenerate, com veículos com viagens pseudo-aleatórias por meio do script randomTrips.py.
      - Utilização de seeds para tornar eventos aleátorios determinísticos, garantindo reprodutibilidade.
    2. Abordagem da Simulação Proposta:
      - Iniciar a simulação com as configurações definidas;
      - Inserir veículos com viagens pseudo-aleatórias conforme seed;
      - Gerar acidentes pseudo-aleatórios de maneira pré-determinada;
      - Despachar veículos de emergência para atender aos acidentes, com atraso propósital e priorização de acidentes com menor deadline para simular de forma mais fidedigna a realidade;
      - Aplicar o algoritmo Green Wave no controle dos semáforos para auxiliar os veículos de emergência, em conjunto com algoritmo  EDF para abrir os sinais para os VEs que estão atendendo aos acidentes mais críticos (ativado somente com o fator Algorithm: Green Wave);
      - Encerrar a Simulação quando todos os veículos completarem suas viagens ou todos os acidentes forem resolvidos.
      - Coletar os resultados;
    3. Abordagem da Proposta do Green Wave com EDF:
      - Busca todos os veículos de emergência ativos, ordenados pelo menor deadline e atendimento mais velho; *
      - Para cada veículo de emergência, verifica os próximos sinais de trânsito à 300 metros de distância:
        - Verificar se o sinal já está sendo alocado por algum outro VE com deadline mais crítico;
        - Se não, inserir os dados necessários no buffer;
      - Para cada registro no buffer:
        - Verificar a fase atual e adotar a estratégia adequada:
          - INITIAL_TRANSITION:           iniciar a modificação dos sinais.
          - IN_PROGRESS:                  manter aberto o sinal para a via do VE e fechar para as demais vias.
          - FINAL_TRANSITION:             tornar amarelo o sinal que o VE estava e manter fechada as demais vias.
          - RETURN_TO_PROGRAM_ORIGINAL:   retornar o sinal ao modo original.
        - Atualizar status do registro para a próxima fase, se necessário.
        - Verificar se o veículo de emergência já passou pelo sinal para finalizar o Green Wave.
  - ## Carga de Trabalho (APPROACH PROPOSED)
     - Código da solução em Python
     - Scripts do SUMO para criação da rede viária e dos veículos
     - Envio de requisições do TraCI API para a simulação 
     - Simulador SUMO.
        - Utilização da biblioteca argparse para modificar parâmetros
        - Projetar a carga de trabalho que melhor representa as diferenças entre as abordagens com e sem Green Wave
  - ## Execução dos Experimentos (experimental results)
    - Planejamento de Projeto Fatorial
    - k = 4 (número de fatores)
    - n = 2^k = 2^4 = 16 combinações
    - Utilização de 10 seeds pré-determinados
    - Total de testes: nº seeds * nº de combinações = 10 * 16 = 160 testes
    ### Fatores Primários selecionados e seus respectivos níveis:
      1. Frequência de Acidentes por Minuto: 0.6 ou 1.2 por minuto
      2. Tempo de Atraso no Despacho do VE: 30 ou 120 segundos
      3. Modelo de Seguimento de Carro: Krauss ou EIDM
      4. Algoritmo de Controle dos Semáforos
          1. Padrão (temporizado com ciclo fixo, sem Green Wave)
          2. Padrão com Green Wave (acionado apenas na presença de veículos de emergência)
    ### Fatores Secundários:
      - Número de veículos: 4800
      - Número de vias acidentadas: 4
      - Distância do veículo de emergência aos semáforos para acionamento do Green Wave: 300 metros
      - Tempo de bloqueio inicial de criação de acidentes: 300 segundos
      - Quantidade máxima de acidentes numa mesma via: 1
      - Tempo de simulação: 1200 segundos
      - Comprimento da via: 300 metros
      - Tempo de transição de fases do Green Wave: 8.0 segundos
      - Distância mínima do veículo de emergência ao veículo acidentado para resolução do acidente na via: 15 metros
      - Gravidade do Acidente e Golden Time:
        - Crítico: 850
        - Alto: 1000
        - Médio: 1200
        - Baixo: 1500
      - Velocidade permitida da via: 13.89 m/s (default SUMO)
      - Velocidade da via acidentada: 1.0 m/s
  - ## Analise dos resultados (experimental results)
  - ## Gráficos (experimental results)
    - Fatores com interação (retas que se intersectam)
    - Fatores sem interação  (retas que não se intersectam, paralelas)
  - ## Conclusão (experimental results)
    



### Detalhes da Simulação

## Geração de Acidentes
  - Acidentes ocorrem de forma períodica durante a simulação, onde um veículo não-emergência e não-acidentado é selecionado em uma via elegível para acidentes, o veículo é configurado a parar próximo ao meio da via e a via fica com velocidade permitida de 1.0 m/s
      - Por quê próximo ao meio da via?
        - Paradas próximas as saídas impedem que veículos façam a mudança de faixa para conseguir entrar em outra via
        - Paradas próximas as entradas podem impedir de veículos entrarem na via acidentada.
        - Esses dois casos entram nas melhorias futuras que a solução pode embarcar para avaliar a otimização de forma completa, exaurindo todos os casos possíveis.
      - Quando uma via é elegível para acidentes:
        - foi definido na simulação proposta a quantidade de 4 vias elegíveis por simulação.
        - também é verificado se na via existe algum acidente em curso, pois só pode existe um acidente por via
        - a escolha das vias é aleatória.
      - O tráfego nas vias acidentadas apresentam velocidade relativa abaixo de 0.1, o que configura o nível de serviço para F, referenciado pelo LOS (Level of Service by Transportation)
      - Enquanto o acidente não é resolvido, a vazão de veículos continua prejudicada em conjunto com veículos que continuam chegando neste fluxo, há um espalhamento do congestionamento para as vias próximas. E um congestionamento muito grande pode gerar deadlocks complexos, assim inviabilizando a avaliação do cenário.
      - Quando acontece um deadlock, a resolução é o teleport de veículos, configurado pelo parâmetro time-to-teleport que está definido com 300 segundos, padrão do SUMO.
      - O evento chave na diferenciação entre os dois modelos foi com a presença de congestionamentos nos cenários. Foi necessário identificar os fatores fortemente relacionados ao aumento de congestionamentos, como volume de veículos na simulação, redução de velocidade da via acidentada, maior quantidade de acidentes na simulação, modelo de seguimento de carro ou o atraso do despacho do veículo de emergência. Assim, foi regulado seus níveis de modo que pudessemos ter cenários o mais congestionado possíveis e que não apresentasse deadlocks ou que fosse o mínimo possível, para não inviabilizar a simulação.
      - No cenário que estamos apresentando existem deadlocks, porém com baixa incidência que possibilitaram os experimentos.
  
  ## Atendimento do VE
  - Um controlador na solução verifica de forma períodica se existe novos acidentes na simulação para associar o atendimento mais crítico a um veículo de emergência. A viagem do VE iniciará de acordo com o nível de atraso do despacho regulado.
    - O VE será despachado de um HOSPITAL_START, que seguirá até o local do acidente e finalizará a viagem se deslocando para HOSPITAL_END.
      - HOSPITAL_START e HOSPITAL_END são duas vias que são definidas de forma aleatória no início da simulação.
      - Os critérios de seleção das vias são:
        - Vias não-internas de cruzamentos
        - Não são vias elegíveis a acidentes.
    - Durante o percurso do atendimento, o VE é monitorado em tempo real com a infraestrutura (V2I) para verificar:
      - Se GWA ativo, para abrir os semáforos do caminho.
      - Se já chegou ao local de acidente para remoção do veículo acidentado e resolução da velocidade da via
      - Se já chegou ao hospital de destino para verificar se o prazo estipulado foi atendido.
   
  ## Comportamento dos veículos normais durante o acidente
  - Há um monitoramento dos veículos normais que estão na mesma faixa e atrás do veículo acidentado para realizarem uma mudança de faixa temporária apenas para ultrapassar o veículo acidentado, e retornar para a faixa original, assim não travando o tráfego.
  - Veículos a frente do VE formam uma faixa virtual liberando a passagem. Essa faixa virtual é definida pelos parâmetros lateral-resolution e device.bluelight.reactiondist com valores respectivos de 1.8 e 1.0. Foi percebido que faixas virtual extensa tendia prejudicar a avaliação do cenário, pois veículos que estavam já ponta extrema para seguir para outra via eram obrigatóriamente deslocados para uma faixa que não permitia a conversão para a via requisitada. Assim, o veículo ficava em modo de deadlock e travando todos os veículos anterior a ele que não poderiam fazer a passagem para a via requerida.
   
   
   
   
   
   
    - Obtemos os dados das métricas selecionadas para avaliação através do script de geração de relatório *tripinfo-output* e *edgedata-output* disponibilizado pelo SUMO, e as métricas customizadas via código da solução em Python.
    - A carga de trabalho é facilmente modificada utilizando a biblioteca argparse da linguagem Python na modificação dos parâmetros.
