from config import (
    traci,
    settings,
)


def improve_traffic_on_accidented_road():
    if len(settings.buffer_emergency_vehicles) > 0:
        vehicles = traci.vehicle.getIDList()
        for emergency_vehicle in settings.buffer_emergency_vehicles:
            accidented_road_id = emergency_vehicle['accidented_road_id']
            for veh_id in vehicles:
                type_id = traci.vehicle.getTypeID(veh_id)
                # para reroute os veículos de emergência, precisa se preocupar com o destino meio que está socorrendo a vítima, a fazer
                if type_id != 'emergency_emergency':
                    next_roads_list = traci.vehicle.getRoute(veh_id)
                    if accidented_road_id in next_roads_list:
                        traci.edge.adaptTraveltime(accidented_road_id,traci.edge.getTraveltime(accidented_road_id))
                        traci.vehicle.rerouteTraveltime(veh_id)
                        if next_roads_list[-1] == accidented_road_id: 
                            traci.vehicle.setColor(veh_id, color=(0, 100, 100)) # se for a ultima rota
                        elif next_roads_list[0] == accidented_road_id: 
                            traci.vehicle.setColor(veh_id, color=(100, 0, 100)) # se for a primeira rota
                        else:
                            traci.vehicle.setColor(veh_id, color=(0, 255, 0)) # reroute vehicles to avoid of the aciddented road