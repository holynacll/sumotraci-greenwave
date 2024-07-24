Docs:
  - https://sumo.dlr.de/pydoc/

Cenário:
 - [ ] utilizar mapa de brasília (verificar possibilidade de fechar numa região, ex: ceilandia)
 - [ ] configurar demanda de veículos randômica
 - [ ] importar demanda de veículos de emergência/acidente de trânsito das bases do SAMU/DETRAN-DF
 - [ ] abordagem:
   - [x] deadline de vidas - classificação (ex: baixo, médio, grave, gravíssimo, ...)
   - [x] EDF com prioridade
   - [X] green wave com escalonamento
    - [x] traffic light logic complete for green wave
   - [x] reroute de veículos para evitar via com acidente

  TODO
   - [ ] article: Analysis and modelling of road traffic using SUMO tooptimize the arrival time of emergency vehicles
   - [ ] modelagem da demanda de veículos
    - [ ] pegar demanda de veículos de emergência/acidentes que ocorrem na base do samu
      - [ ] explicar possíveis impactos que cada variável pode causar no trânsito e no algoritmo.
      - [ ] comparar estatisticas de:
        - [ ] chamados que a samu recebe
        - [ ] chamados que veículos de emergência sai na rua
        - [ ] chamados que veículos de emergência sai na rua com acidente de trânsito
        - [ ] no final: focar em uma região de brasília, ex: Ceilândia
        - [ ] comparar com os dados dos relatórios do DETRAN/DF
    - [ ] demanda de veículos de brasília/ceilândia (verify)
    - [ ] envia veiculo de emergencia do bombeiro/policia para fazer o despacho do veiculo acidentado (novo cenário de acidente)
    - [ ] article: Modelling green waves for emergency vehicles using connected traffic data
      - [ ] priorizacao do VE
      - [ ] veiculos comuns priorizar veiculos de emergencia (dar passagem) changelane
      - [x] proibir retorno dos veiculos na mesma via
      - [ ] verificar parada de VE com bluelight
      - [ ] implementar transição mais suave de fechamento de sinal (impacto colateral dos sinais adjacentes)
        - [ ] implementar buffer listener para transição, se duração para mudar de vermelho para verde for < MIN_LIMIT_ESTIPULADO_DUR, então reduz o tempo de duração e atribui um buffer / listerner marcando até ficar verde, e sai do listener / buffer
   - [ ] limitar e parametrizar tempo de simulação
   - [ ] criar hospitais parametrizavel
   - [ ] parametrizar as váriaveis do cenário
   - [x] configurar parada do veículo de emergência no local do acidente
   - [ ] customizar/alternar algoritmos de roteamento
   - [ ] Green-Wave Traffic Theory Optimization and Analysis
   - [ ] Detectores para simular RSUs (ao inves de ter uma solução de monitoramento global, seria monitorando os VEs que estivessem no raio dos RSUs)

var resposta
meanSpeedRelative (velecidade media / velocida permitida)
meanSpeed
lossTime
consumo CO2 report

OBS:
dados abertos sobre a malha rodoviária de brasília - https://geoservicos.detran.df.gov.br/geoserver/web/wicket/bookmarkable/org.geoserver.web.demo.MapPreviewPage;jsessionid=F08C73149B32FCDEF43E0E34F2F9A086?0&filter=false


0.1 - $SUMO_HOME = "C:\Users\Alexandre Cury\miniconda3\envs\sumo-env\Lib\site-packages\sumo"
0.2 - export SUMO_HOME="/home/acll/miniconda3/envs/sumo-env/lib/python3.11/site-packages/sumo"

1 - netgenerate --grid --grid.number=4 --grid.length=300 --default.lanenumber 3 --default-junction-type traffic_light --output-file=data/road.net.xml --no-turnarounds true --junctions.join-turns true
  1.1 - to save
  netgenerate --grid --grid.number=5 --grid.length=300 --grid.attach-length 200  --default.lanenumber 3 --default-junction-type traffic_light --output-file=data/road.net.xml --no-turnarounds true --no-left-connections true
  1.2 - netgenerate --grid --grid.number=5 --grid.length=200 --default.lanenumber 3 --default-junction-type traffic_light --output-file=data/road.net.xml --no-turnarounds true --fringe.guess true --fringe.guess.speed-threshold 5.5
  <!-- netgenerate --rand --default.lanenumber 2 --default-junction-type traffic_light --output-file=data/road.net.xml --no-turnarounds true --no-left-connections true  -->
  <!-- --no-internal-link -->

2.0 - python $SUMO_HOME/tools/randomTrips.py -n road.net.xml -r route.rou.xml --seed 42 --validate --fringe-factor 1000 -p 1
2.1 - python $SUMO_HOME/tools/randomTrips.py -n road.net.xml -r route.rou.xml --seed 42 --validate --fringe-factor 1000 -p 2

3 - add below code on first line into <routes> of the file route.rou.xml
  <vType id="emergency_emergency" vClass="emergency" color="red" speedFactor="1.5">
    <param key="has.bluelight.device" value="true"/>
  </vType>

4 - python main.py

bibliografia:
Analysis and Modelling of Road Traffic Using SUMO to Optimize the Arrival Time of Emergency Vehicles - https://www.tib-op.org/ojs/index.php/scp/article/view/225/428 - https://www.youtube.com/watch?v=GlPf7TmuI9E (verificar o algoritmo)
Intelligent traffic management for emergency vehicles with a simulation case study - https://www.youtube.com/watch?v=7rpXvYsNFIE
A Programmer's Note on TraCI_tls, TraCI, and SUMO - https://intelaligent.github.io/tctb/post-learning-traci-tls.html
Quantifying the impact of connected and autonomous vehicles on traffic efficiency and safety in mixed traffic
https://core.ac.uk/download/pdf/147323687.pdf
https://easychair.org/publications/open/6KGt
https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber=9264154
https://www.researchgate.net/publication/328406378_Urban_Traffic_Optimization_with_Real_Time_Intelligence_Intersection_Traffic_Light_System
https://people.engr.tamu.edu/guni/Papers/NeurIPS-signals.pdf
https://arxiv.org/pdf/2107.10146.pdf
Simulation of accident with V2X communication using SUMO-TraCI-Veins - https://www.youtube.com/watch?v=7TXngtcCPz4

refs:
Lane-Changing Model in SUMO
https://arxiv.org/pdf/2304.05982.pdf
https://cst.fee.unicamp.br/sites/default/files/sumo/sumo-roadmap.pdf
https://github.com/eclipse-sumo/sumo/issues/4312
https://www.researchgate.net/publication/37454736_TraCI_An_Interface_for_Coupling_Road_Traffic_and_Network_Simulators?enrichId=rgreq-481d19cd502f6889985e24af3c6715e4-XXX&enrichSource=Y292ZXJQYWdlOzM3NDU0NzM2O0FTOjk5NzQ2NDUwNTA5ODMyQDE0MDA3OTI4MTY1NTY%3D&el=1_x_3&_esc=publicationCoverPdf



bugs:
cars not stopping on red light: https://sourceforge.net/p/sumo/mailman/message/30703209/




 1935  python $SUMO_HOME/tools/randomTrips.py -n road.net.xml
 1936  python $SUMO_HOME/tools/assign/duaIterate.py -n road.net.xml -t trips.trips.xml -l 10
 1941  python $SUMO_HOME/tools/assign/one-shot.py -f 200 -n road.net.xml -t trips.trips.xml
 1942  python $SUMO_HOME/tools/randomTrips.py -n road.net.xml --seed 42 --validate
 1943  python $SUMO_HOME/tools/assign/one-shot.py -f 200 -n road.net.xml -t trips.trips.xml
 1948  python $SUMO_HOME/tools/randomTrips.py -n road.net.xml --seed 42 --validate
 1949  python $SUMO_HOME/tools/assign/one-shot.py -f 200 -n road.net.xml -t trips.trips.xml
 1957  netgenerate --grid --grid.number=2 --grid.length=150 --default.lanenumber 2 --default-junction-type traffic_light --output-file=road.net.xml
 1959  netgenerate --grid --grid.number=3 --grid.length=150 --default.lanenumber 2 --default-junction-type traffic_light --output-file=road.net.xml
 1968  netedit road.net.xml 
 1970  python $SUMO_HOME/tools/randomTrips.py -n road.net.xml --seed 42 --validate --fringe-factor 1000
 1971  netgenerate --grid --grid.number=3 --grid.length=150 --default.lanenumber 2 --default-junction-type traffic_light --output-file=road.net.xml
 1972  python $SUMO_HOME/tools/assign/one-shot.py -f 10 -n road.net.xml -t trips.trips.xml



Observações:
 - vehicles ainda possuem comportamentos estranhos, invês de avançar quando deveria, se mantém parado...
 - condições de prioridades entre veículos de emergência e veículos normais tem que melhorar
 - os inputs e outputs das junctions tão sendo obstaculos grandes