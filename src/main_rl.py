from config import (
    traci,
    checkBinary,
    tc,
    settings,
)
import argparse
import os
import sys
import pickle

import pandas as pd


from sumo_rl import SumoEnvironment
from sumo_rl.agents import QLAgent
from sumo_rl.exploration import EpsilonGreedy
import numpy as np

os.environ['LIBSUMO_AS_TRACI'] = "1"


def patched_encode(self, state, ts_id):
    """Encode the state of the traffic signal into a hashable object."""
    phase_idx = np.where(state[: self.traffic_signals[ts_id].num_green_phases] == 1)[0]
    if len(phase_idx) > 0:
        phase = int(phase_idx[0])
    else:
        phase = 0
    min_green = state[self.traffic_signals[ts_id].num_green_phases]
    density_queue = [self._discretize_density(d) for d in state[self.traffic_signals[ts_id].num_green_phases + 1 :]]
    # tuples are hashable and can be used as key in python dictionary
    return tuple([phase, min_green] + density_queue)

SumoEnvironment.encode = patched_encode


if __name__ == "__main__":
    alpha = 0.1
    gamma = 0.99
    decay = 1
    runs = 30
    episodes = 4

    env = SumoEnvironment(
        # net_file="src/sumo_rl_experiments/nets/4x4-Lucas/4x4.net.xml",
        # route_file="src/sumo_rl_experiments/nets/4x4-Lucas/4x4c1c2c1c2.rou.xml",
        net_file="data/road.net.xml",
        route_file="data/route.rou.xml",
        use_gui=True,
        num_seconds=3600,
        min_green=5,
        delta_time=5,
    )

    for run in range(1, runs + 1):
        initial_states = env.reset()
        ql_agents = {
            ts: QLAgent(
                starting_state=env.encode(initial_states[ts], ts),
                state_space=env.observation_space,
                action_space=env.action_space,
                alpha=alpha,
                gamma=gamma,
                exploration_strategy=EpsilonGreedy(initial_epsilon=0.05, min_epsilon=0.005, decay=decay),
            )
            for ts in env.ts_ids
        }

        for episode in range(1, episodes + 1):
            if episode != 1:
                initial_states = env.reset()
                for ts in initial_states.keys():
                    ql_agents[ts].state = env.encode(initial_states[ts], ts)

            infos = []
            done = {"__all__": False}
            while not done["__all__"]:
                actions = {ts: ql_agents[ts].act() for ts in ql_agents.keys()}

                s, r, done, info = env.step(action=actions)

                for agent_id in s.keys():
                    ql_agents[agent_id].learn(next_state=env.encode(s[agent_id], agent_id), reward=r[agent_id])

            env.save_csv(f"outputs/4x4/ql-4x4grid_run{run}", episode)
        
        # for ts_id, agent in ql_agents.items():
        #     model_name = f"outputs/4x4/model_run{run}_{ts_id}.pkl"
        #     with open(model_name, "wb") as f:
        #         pickle.dump(agent.q_table, f)
        #     print(f"Q-Table salva em: {model_name}")

    env.close()
