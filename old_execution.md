
0.1 - $SUMO_HOME = "C:\Users\Alexandre Cury\miniconda3\envs\sumo-env\Lib\site-packages\sumo"
0.2 - export SUMO_HOME="/home/acll/miniconda3/envs/sumo-env/lib/python3.11/site-packages/sumo"

1 - netgenerate --grid --grid.number=4 --grid.length=300 --default.lanenumber 3 --default-junction-type traffic_light --output-file=data/road.net.xml --no-turnarounds true --junctions.join-turns true
  1.1 - to save
  netgenerate --grid --grid.number=5 --grid.length=300 --grid.attach-length 200  --default.lanenumber 3 --default-junction-type traffic_light --output-file=data/road.net.xml --no-turnarounds true --no-left-connections true
  1.2 - netgenerate --grid --grid.number=5 --grid.length=200 --default.lanenumber 3 --default-junction-type traffic_light --output-file=data/road.net.xml --no-turnarounds true --fringe.guess true --fringe.guess.speed-threshold 5.5

2.0 - python $SUMO_HOME/tools/randomTrips.py -n road.net.xml -r route.rou.xml --seed 42 --validate --fringe-factor 1000 -p 1
2.1 - python $SUMO_HOME/tools/randomTrips.py -n road.net.xml -r route.rou.xml --seed 42 --validate --fringe-factor 1000 -p 2

3 - add below code on first line into <routes> of the file route.rou.xml
  <vType id="emergency_emergency" vClass="emergency" color="red" speedFactor="1.5">
    <param key="has.bluelight.device" value="true"/>
  </vType>

4 - python main.py



bugs and debug:
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