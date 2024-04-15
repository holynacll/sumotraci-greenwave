"""title: Analysis and modelling of road traffic using SUMO tooptimize the arrival time of emergency vehicles
"""

"""Há inúmeros estudos de priorização de veículos de emergência em cidades no mundo todo, mas toda area é única,
o que requer uma coleção de dados e simulação a serem feitos separadamente
"""

"""O foco nesse trabalho é a cidade X, uma das mais movimentadas, muitos cruzamentos e retornos, muitas váriaveis a serem analisadas. 
O estudo apresentará a modelagem da demanda, a simulação e avaliação de estratégias de melhoria do tráfego para veículos de emergência.
"""

"""Para realizar uma simulação de tráfego precisa, é necessário a garantia de qualidade dos dados de entrada e a limpeza dos dados mestres

Duvida: O que são dados mestres?
"""

"""A demanda veícular é calibrada pelos dados de contagem de tráfego fornecidos pelo "Detran/BA"
"""

"""Para calibrar o tráfego rodoviário e a rede rodoviária, são geradas matrizes de origem e destino usando o modelo matemático da gravidade 
(Gravity Mathematical Model) e o OpenStreetMaps. Este é um processo demorado e requer esforço. Porém, é necessário para termos uma simulação
mais precisa com o mundo real.
"""

"""A simulação do tráfego rodoviário é feita utilizando o SUMO (Simulation of Urban mobility). E os indicadores de performance chaves 
(Key Performance Indicators), relevantes para avaliação da simulação serão: tempo de viagem total e tempo de atraso total.

KPI-1: tempo de viagem total
KPI-2: tempo de atraso total
"""

"""O cenário do mundo real é comparado com cinco cenários alternativos. A comparação dos KPIs revelaram que o mundo real teve resultados
de tempo de viagem total maior comparado com os propostos algoritmos de priorizações de veículos de emergência.
Os tempos de viagem dos VEs diminuíram significamente. Levando em consideração que cada segundo poupado podem ser cruciais.
"""

"""Introdução....
crescente aumento das taxas de urbanização
avanços no setor de transportes
alta taxa de mobilidade urbana
Busca por maior conforto e qualidade de vida

consequências:
congestionamentos,
acidentes,
questões ambientais (greenhouse gases, carbon emission, particulates, CO2, ...)

soluções:
estratégias de melhoria do tráfego
  - car pool lane (faixas de partilha de veículos)
  - espaço dedicado para pedestres e ciclistas
"""

"""Testar e implementar essas estratégias requerem uma investigação e análise prévia. Sem estes estudos, 
as estratégias e políticas implementadas poderiam não ser viáveis e acabar por custar mais em termos de 
infraestutura, tempo, vidas. Para ter uma avaliação teórica e prever os resultados dessas estratégias/medidas/soluções,
a simulação desempenha um papel essencial.
"""

"""Para uma simulação ser implementada adequadamente, os seguintes elementos são necessários 
    - Uma rede de dados que contemplem estradas, trilhas, rotas de bondes, ... (road network)
    - Infraestrutura de dados adicionais como sinais de trânsito, loops de indução, ... 
    - Demanda do tráfego (route.rou.xml/trips.trips.xml)
    - Restrições de trânsito, como velocidade limite, locais de construção, linhas de ônibus
"""

"""É um trabalho demorado, que requer esforço para preparar o modelo de simulação de trânsito.
Já existem modelos de simulação prontos para uso, como [2] da cidade de Bologna, para testar suas 
estratégias de melhoria de tráfego, economizando tempo e esforço necessários para simulação. 

 [2] L. Bieker, D. Krajzewicz, A. P. Morra, C. Michelacci, and F. Cartolano, “Traffic simulationfor all:
 A real world traffic scenario from the city of bologna,” inSUMO 2014, May 2014.[Online]. Available:https://elib.dlr.de/89354/.
"""

"""Um dos principais da simulação de trânsito é avaliar diferentes estratégias de melhorias do tráfego. Este estudo mostra 
outra estratégia de melhoria do tráfego baseado em veículos de emergência.
"""

"""
"Um veículo de emergência é um veículo que é usado por serviços de emergência para responder a um incidente." [3] Wikipedia
Mesmo uma pequena redução no tempo de chegada (arrival time) dos EVs (bombeiros, ambulância, polícia) podem salvar vidas. 
Para lidar com essas situações, os EVs tem direitos especiais, como violar sinais vermelhos, ao se aproximar de um cruzamento de
semáforos (traffic light junction, TLJ), ou viajar em direção oposta para reduzir o tempo de chegada.

Estas abordagens acabam precisando de melhorias, há momentos que VEs ficam presos em uma longa fila de veículos em frente ao TLJ 
ou ficam presos em um conjestionamento de trânsito onde não há como ultrapassar.
"""

"""O principal objetivo do estudo é simular o tráfego viário da região X, na área Y, em Z. Seguido pelo estudo e avaliação 
de diferentes cenários para otimizar o tempo de chegar de VEs.
"""
    
"""Este paper é organizado da seguinte forma... discussões detalhadas sobre master data, pré-processamento dos dados, modelagem de 
dados e processo de simulação, modificações e adequações da rede e geração do tráfego. Section 3 explica a metodologia da solução e 
os diferentes cenários para VEs. Section 4 mostra os resultados obtidos. Section 5 apresenta a conclusão e futuros trabalhos.
"""    

"""Master data:
O diagrama de fluxo de dados baseado na metodologia Gane-Sarson Master Data consiste em
 - rede viária
 - com dados adicionais de infraestrutura e restrições de trânsito
 - contagem de veículos agregados por 24 horas. 

A contagem veícular é fornecida na forma de shapefile na localização da área geográfica.
A rede de tráfego é importada do OpenStreetMaps

A metodologia Gravity Model, de 
    (
        W. A. Martin and N. A. Mcguckin, “Nchrp report 365: Travel estimation techniques forurban planning,
        ”TRB, National Research Council, Washington, DC, vol. 18, p. 21, 1998.
    )
é usada para calcular as Matrizes Origem e Destino (ODMs), com referência ao planejamento 
do tráfego essa metodologia afirma que:
 
 O numero de viagens totais e o numero de viagens produzidas por cada TAZ são obtidos pelo DETRAN/BA (shapefile)
 
 Ficou confuso para mim como foi gerado a matriz de origem e destino, utilizando a abordagem do Gravity Model, com
 a contagem de viagens fornecidas pelo shapefile. Mas, de alguma forma foi gerado os ODMs.
 
 Com as matrizes produzidas, foi gerado um modelo de demanda através de recursos do SUMO, como od2trips e duarouter.
 
 que fornece as rotas, carros, pedestres, bondes, transportes públicos, etc. para simulação do trânsito no SUMO.
"""

    """topico 3: Solution Methodology, Case Scenarios and Study Area
    
    3.1: Solution Methodology
    Estudos realizados para otimizar o tempo de chegada (arrival time) de veículos de emergência:
      - otimização no roteamento e despacho de VEs que podem levar a rotas mais rápidas
        - "An optimization model for real-time emergency vehicledispatching and routing", 2003
      - ranking de alternativas de roteamento emergêncial
        - "Ranking of alternatives for emergency routing on urbanroad networks,", 2015
    
    Entretanto, comportamento de pedestres, especialmente crianças são imprevisíveis e mesmo que o SUMO possa 
    ser usado para modelar tais padrões, o mundo real não irá funcionar exatamente como na simulação.
    
    No caso do reroteamento de um VE, o algoritmo prioriza a rota mais curta e livre de tráfego. Mas, o caminho 
    mais curto poderia incluir áreas residenciais que consistema em mais tráfego de pedestres em comparação com as 
    ruas principais.

    Dessa forma, a abordagem "preferida" nesse estudo é a abordagem de priorização de EV usando comunicação V2X 
    (Veículo para Infraestrutura), comunicando com TLJ. Essa abordagem é adotada em:
     - "Modelling green waves for emergency vehicles usingconnected traffic data", 2019
     - "Cooperative traffic management for emergency vehicles in the city of bologna", 2017
     - "Emergency vehicle prioritization using vehicle-to-infrastructure communication", 2011
    
    A abordagem básic é que assim que o EV chega ao TLJ, o semáforo muda para verde para a direção da viagem 
    do VE e prioriza o EV.
    
    As seguintes etapas são realizadas para a aplicação de priorização do EV, também conhecida com abordagem 
    WALABI:
     - EV envia CAMs (mensagem de concientização cooperativa) e informações de rota
     - Unidade de beira de estrada (RSU) informa ao Centro de Gerenciamento de Tráfego (TMC)
     - TMC define semáforos na rota do EV: verde para o EV e vermelho para todos os outros participantes do trânsito
     - Após o EV passar pela intersecção, a operação normal continua
     
    Para a abordagem de priorização de EV mencionada acima, surge a questão de qual modelo ideal de distância 
    entre um EV e um semáforo, para que o semáforo fique verde.
    
    O estudo de (
        "Cooperative traffic management for emergency vehicles in the city ofbologna"
    ) mostra que ao EVs entrarem na faixa de 300 metros do TLJ, o TLJ já fica verde. E quando saírem, a intersecção 
    volta a operar normal.
    
    Portanto, 300 metros são considerados como valor limite (threshold distance value). (para o cenário 2)
    
    Há uma consequência negativa de ter esse valor pré-definido que é para os demais veículos que estão aguardando 
    na frente do sinal vermelho. Se a fase vermelha do semáforo aumentar, o congestionamento do outro lado também poderá 
    aumentar, levando a mais caos e mais tempo para difundir o congestionamento.
    
    Portanto, para resolver esse problema, em vez de assumir um valor predefinido, ele é calculado dinâmicamente 
    (dynamically calculating threshold distance). Esse threshold distance (valor de distância limite) é calculado 
    usando a velocidade do EV (speed) e o número de veículos esperando em frente ao TLJ. Abordagem feita pelo 
    "Modelling green waves for emergency vehicles usingconnected traffic data".
    
    Eq (1) - Tfree= (Nwaiting+ 1)∗tB+tsafety
    Tfree = tempo necessário para deixar o EV passar o TLJ
    Nwaiting = número de veículos esperando em frente ao TLJ
    tsafaty = tempo de segurança, const = 3 seconds
    tB = tempo requerido para um veículo passar a intersecção, const = 1.8 seconds
    
    distance = Tfree * Vev (speed EV)
    """

    """3.2 Emergency Vehicle Priorization Study Area
    O caminho destacado abaixo na figura 3 é a rota dos EVs cujo comportamento é avaliado na simulação.
    
    O comprimento da rota é de 1.5 km, consistindo de 3 grandes e 2 pequenas interseções 
    """
    
    """3.3 Case Scenario
    
    duas suposições para comparar
    Sup A - condição de tráfego usual
    Sup B - suposição de via fechada por incidente/construção/... (somente uma via se mantém disponível)
    
    Cenários:
      1 - Sem prioridade para EVs - Sup A
      2 - Com priorização para EVs, com distância predefinida de 300 metros - Sup A
      3 - Com priorização para EVs. com distância dinâmica - Sup A
      4 - Sem prioridade para EVs - Sup B
      5 - Com priorização para EVs, com distância predefinida de 300 metros - Sup B
      6 - Com priorização para EVs. com distância dinâmica - Sup B
    
    Para gerar tráfego de maneira realista, os dados dos induction loops são usados. Esses dados é higienizado, 
    calculados e normalizados sobre o número total de carros, que resulta na criação do fluxo de distribuição de 
    demanda sobre o tempo, ao decorrer de um dia.
    
    Um gráfico é mostrado com X como o tempo repartido em [hh:mm] e o eixo Y representa a media da taxa normalizada 
    do tráfego geral.
    
    O pico, isto é, a contagem média máxima é medida por 3 minutos por volta das 8h, contado 30 carros. O congestionamento 
    começa a partir das 7h e vai até as 10h30.
    
    Esse foi o intervalo de tempo selecionado para testar nossa simulação. Um total de 10 EVs são despachados entre esse 
    intervalo de tempo e o *tempo de atraso* e o *tempo de viagem* são comparados.
    """
    
    """4 - Results
    
    """