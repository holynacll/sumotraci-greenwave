# Processo Experimental Sistemático
  - ## Problema:
    - É preciso que os veículos de emergência tenham um caminho mais livre possível. Veículos de Emergência tem passe livre para passar de sinais vermelhos, porém com o alto volume veículos no trânsito, aliado ao controle dos semáforos padrão (abre e fecha de forma temporizada), congestionamentos podem ser produzidos no caminho por onde o veículo de emergência irá passar. Nesse momento, os veículos normais se tornam obstáculos que não permitem a passagem do veículo de emergência, prejudicando na duração da viagem. 
  - ## Pergunta:
    - De que forma é possível melhorar o trânsito para que o veículo de emergência tenha um caminho mais livre possível?
    - Modificando o comportamento do controle de sinais de trânsito para que se abram a medida que veículos de emergência se aproximem, fazendo com que o fluxo do caminho que o veículo de emergência percorre melhore, onde os veículos normais vão deixar de ser obstáculos parados em frente ao veículo de emergência, e consequentemente o fluxo do veículo de emergência melhore também. Dessa forma, reduzindo a duração da viagem.
  - ## Métricas selecionadas:
    - Duração da viagem (segundos)
    - Tempo perdido na viagem (somátorio do tempo de paradas, quando velocidade do veículo == 0 por pelo menos > 0.01 segundo, começa a contar o tempo perdido) (segundos)
    - Quantificação das ocorrências de acidentes salvos e não salvos de acordo com deadline (int)

  - ## Parâmetros identificados:
    - Número de veículos: 4800
    - Frequência de acidentes: 1 acidente a cada 50 ou 100 segundos (selecionado)
    - Tempo de atraso no envio de veículo de emergência: 30 ou 120 segundos (selecionado)
    - Modelo de seguimento de carro: Krauss ou EIDM
    - Algoritmo de controle dos semáforos: Padrão Temporizado ou Green Wave
    - Número máximo de vias acidentadas: 4
    - Distância do veículo de emergência ao semáforo para, para acionamento do green wave: 300 métros
    - Tempo de bloqueio para novo acidente em uma via que acabou de resolver um acidente: 300 segundos
    - Quantidade máxima de acidentes numa mesma via: 1
    - Tempo de simulação, onde serão gerados acidentes e disparado veículos de emergência para atender os acidentes (O tempo total da simulação será o tempo até que todos os veículos inseridos na simulação tenham completado suas viagens, ou que todos os acidentes gerados tenham sido resolvidos e os veículos de emergência tenham completado sua viagem (saída do hospital -> local do acidente -> hospital de destino), logo tempo de simulação será diferente do tempo total da simulação): 1200 segundos
    - Comprimento da via: 300 métros
    - Tempo de transição de sinais do green wave: 8.0 segundos
    - Velocidade da via: 13.89 m/s (sumo default)
    - Distância mínima do veículo de emergência ao veículo acidentado para resolver o acidente na via: 15.0 métros
    - Via do Hospital de Dispacho do veículo de emergência: random
    - Via do Hospital de Destino do veículo de emergência: random
    - Vias que podem receber acidentes: random
    - Gravidade do Acidente e Golden Time específico:
      - Crítico: 850
      - Alto: 1000
      - Médio: 1200
      - Baixo: 1500
    - Velocidade da via acidentada: 1.0 m/s
  - ## Parâmetros Selecionados (Fatores):
    - Frequência de acidentes: 1 acidente a cada 50 ou 100 segundos
     - Tempo de atraso no envio de veículo de emergência: 30 ou 120 segundos após a ocorrência do acidente
    - Modelo de seguimento de carro: Krauss ou EIDM
    - Algoritmo de controle dos semáforos: Padrão Temporizado ou Green Wave
  - Técnica adotada:
    - Simulação de Trânsito utilizando o SUMO (Simulation of Urban MObility) em conjunto com TraCI API integrado com a linguagem de programação Python.
    - A simulação é reproduzida em um cenario modelo de trânsito de Manhattan, gerado pela ferramenta netgenerate (https://sumo.dlr.de/docs/netgenerate.html), onde um número fixo de veículos trafegam com viagens aleatórias na via, por meio do script randomTrips.py (https://sumo.dlr.de/docs/Tools/Trip.html), feito pela comunidade do SUMO.
    - Na simulação são criado acidentes artificiais, reproduzidos através de um veículo selecionado dinâmicamente de forma pseudo-aleatória, que será parado no meio da viagem e a via onde parou ficará com a velocidade reduzida para simular um acidente. Em seguida, é cadastrado um veículo de emergência para socorrer o veículo acidentado. O veículo de emergência é inserido na simulação após o tempo configurado de despacho (DISPATCH), onde inicia a viagem em uma via representada pelo HOSPITAL_POS_START, que segue até o veículo acidentado, e caminha até a via representada pelo HOSPTIAL_POS_END que marca a finalização do atendimento e é verificado o deadline do acidente  incrementando as métricas de SAVEDS e UNSAVEDS.
    - a configuração da via é feita pelo script:  netgenerate --grid --grid.number=4 --grid.length=300 --default.lanenumber 3 --default-junction-type traffic_light --output-file=data/road.net.xml --no-turnarounds true
    - a configuração e geração dos veículo é feita pelo script dinâmicamente executado, antes de todo início de simulação:
    ```
    def generate_routefile(route_filepath: str, trips_filepath: str, seed: int):
    road_filepath = "data/road.net.xml"
    route_filepath = f"data/{route_filepath}"
    trip_attributes_1 = 'type="passenger_idm"'
    cmd = (
        f"python {os.environ['SUMO_HOME']}/tools/randomTrips.py -n {road_filepath} -r {route_filepath}"
        f" -b 0 -e {settings.SIMULATION_END_TIME} -p {((settings.SIMULATION_END_TIME - 0) / settings.VEHICLE_NUMBER)}"
        f" -o {trips_filepath} --validate --fringe-factor 1000"
        f" --seed {seed}"
        f" --trip-attributes '{trip_attributes_1}'"
    )
    os.system(cmd)

    # Parse the existing XML route file
    tree = ET.parse(route_filepath)
    root = tree.getroot()

    add_emergency_vehicle_type_to_route_file(root)
    
    add_passenger_idm_vehicle_type_to_route_file(root)

    # Write the updated XML route file
    tree.write(route_filepath, encoding="UTF-8", xml_declaration=True)


    def add_emergency_vehicle_type_to_route_file(root):
        # Create emergency vehicle type and add it to the XML route file
        new_element = ET.fromstring("""
        <vType
        id="emergency_emergency"
        vClass="emergency"
        color="red"
        minGap="0.5"
        >
            <param key="has.bluelight.device" value="true"/>
        </vType>
        """)

        # Insert the new element as the first child of the root
        root.insert(0, new_element)


    def add_passenger_vehicle_type_to_route_file(root):
        new_element = ET.fromstring("""
        <vType 
            id="passenger"
            vClass="passenger"
            color="yellow"
            lcCooperative="1.0"
            lcPushy="0.2"
            lcKeepRight="100"
            jmIgnoreKeepClearTime="1.0"
            jmIgnoreJunctionFoeProb="1.0"
            lcTurnAlignmentDistance="1.0"
        >
        </vType>    
        """)

        # Insert the new element as the first child of the root
        root.insert(0, new_element)
    ```
    - a configuração completa da simulação é feita antes de todo início de simulação. Durante a simulação são capturados as métricas especificadas e ao final da simulação serão gerados os relatórios:
    ```
    # this is the main entry point of this script
    if __name__ == "__main__":
    options = get_options()

    # this script has been called from the command line. It will start sumo as a
    # server, then connect and run
    if options.nogui:
        sumoBinary = checkBinary('sumo')
    else:
        sumoBinary = checkBinary('sumo-gui')

    settings.SEED = int(options.seed)
    settings.TIME_TO_BLOCK_CREATE_ACCIDENTS = float(options.time_block_accident)
    settings.DELAY_TO_DISPATCH_EMERGENCY_VEHICLE = float(options.delay_dispatch_emergency_vehicle)
    settings.CAR_FOLLOW_MODEL = options.car_follow_model
    settings.ALGORITHM = options.algorithm

    generate_routefile(
        route_filepath=options.route_filepath,
        trips_filepath=options.trips_filepath,
        seed=settings.SEED,
    )
    update_sumo_config(
        summary_filename=options.summary_filepath,
        route_filename=options.route_filepath,
        new_sumoconfig_filepath=options.sumocfg_filepath,
    )

    # this is the normal way of using traci. sumo is started as a
    # subprocess and then the python script connects and runs
    traci.start([
        sumoBinary,
        "-c", options.sumocfg_filepath,
        "--lateral-resolution", "1.8",
        "--device.bluelight.reactiondist", "1.0",
        # "--emission-output", f'data/{options.emissions_filepath}',
         "--tripinfo-output", f'data/{options.tripinfo_filepath}',
        "-S",
        "-Q",
    ])  

    # Simulation starting
    run()
    
    print('Simulation finished')
    print(settings.ALGORITHM)
    print(settings.CAR_FOLLOW_MODEL)
    print(settings.DELAY_TO_DISPATCH_EMERGENCY_VEHICLE)
    print(settings.TIME_TO_BLOCK_CREATE_ACCIDENTS)
    print('Generating CSV files...')
    tripinfo_xml_to_csv(
        f'data/{options.tripinfo_filepath}',
        f'data/{options.tripinfo_filepath[:-4]}.csv',
    )
    print('CSV files generated!')
    ```
    - A reprodutibilidade será feita através de argparse do python, onde os parâmetros serão passados através de argumentos da chamada do script de simulação. Dessa forma...
  - ## Carga de Trabalho
    - O Código da solução foi desenvolvido na linguagem de programação Python, que através do TraCI API se integra ao SUMO. Dessa forma, para simular o cenário da solução dentro do SUMO é enviado requisições para se comunicar com o cenário para inserir veículo de emergência, remover veículo acidentado, consultar informação de localização, entre outras recursos. Cada requisição dessa é adiciona um overhead na simulação, a carga de trabalho total é calculada com base na simulação programada mais as interações feitas através da integração com a solução. (precisa melhorar esse paragráfo)
    - É dessa forma, que obtemos os dados das métricas selecionadas, seja por script de relatório já definido pelo SUMO, como o *tripinfo-output* utilizado, seja por métricas customizadas como o caso do quantitativo de SAVEDS e UNSAVEDS.
  - ## Execução dos Experimentos
    - será definida pelo método de SS e SST, através da geração do modelo ....
    - serão executados 10 rodadas de testes com seeds diferentes, que serão utilizados para analise...
    - Foram selecionado 4 fatores e 4 váriaveis de respostas. O que será gerado 16 combinações de fatores a ser testado. Dessa forma serão feito 16 combinações * 10 rodadas de teste = 160 testes serão executados.
    - Os outros parâmetros abordados são destacados pela influência que possuem na simulação. os motivos de valores fixados são os seguintes... (trabalhar no planejamento dos experimentos)
    - Analise dos dados...
    - Apresentação
    - Conclusão
    


