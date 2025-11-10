### Improvements

Hoje revisei o código do GWA e percebi que seria bom realizar uma refatoração para melhorar a estrutura geral do projeto. A proposta é organizar o sistema em quatro classes principais, cada uma com responsabilidades bem definidas, que se comuniquem entre si:

 - [] Controlador de VEs: Responsável pelo algoritmo de Earliest Deadline First (EDF) aplicado às Viaturas de Emergência (VEs) em relação aos semáforos.

 - [] Controle Adaptativo de Semáforo: Implementa o algoritmo de transição de estados dos semáforos. No entanto, é necessário melhorar a organização das fases de transição para torná-las mais compreensíveis — outro artigo realizou abordagem semelhante, mas com uma descrição mais clara. É também nesse módulo que pretendo aplicar técnicas de Reinforcement Learning (RL).

 - [] Gerenciamento e Detecção de Incidentes: Responsável por detectar acidentes, alocar recursos, despachar VEs e gerenciar a resolução dos incidentes.

 - [] Infraestrutura (Cloud): Fará a comunicação com o SUMO, realizando a importação dos dados (pull) para as outras classes e o envio de comandos (push) para os semáforos.

 - [] Também é necessário melhorar a documentação do projeto e aplicar boas práticas de desenvolvimento, pois o código está desorganizado — quando escrevi, meu nível de Python ainda era mais básico.



### Observations:
 - vehicles ainda possuem comportamentos estranhos, invês de avançar quando deveria, se mantém parado...
 - condições de prioridades entre veículos de emergência e veículos normais tem que melhorar
 - os inputs e outputs das junctions tão sendo obstaculos grandes