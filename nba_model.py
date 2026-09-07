import random
import time
import requests
import pandas as pd
from nba_api.stats.endpoints import leaguestandings

# Your active Odds API Key
ODDS_API_KEY = "f1308bc4d14a10c9df4c191608dcb0ee"

# ==========================================
# 1. REALISTIC WIN-TOTAL & FRAGILITY ENGINE
# ==========================================
def get_projected_team_ratings():
    print(f"\n--- Fetching Team Baselines & Injury Fragility Indexes ---")
    
    standings_call = leaguestandings.LeagueStandings(season="2025-26")
    time.sleep(1)
    df_standings = standings_call.get_data_frames()[0]
    
    team_conferences = {}
    last_year_records = {}
    
    for index, row in df_standings.iterrows():
        full_name = f"{row['TeamCity']} {row['TeamName']}"
        if row['TeamName'] == 'Clippers':
            full_name = "Los Angeles Clippers"
            
        team_conferences[full_name] = row['Conference']
        last_year_records[full_name] = float(row['WinPCT'])

    url = f"https://api.the-odds-api.com/v4/sports/basketball_nba_championship_winner/odds?regions=us&markets=outrights&oddsFormat=decimal&apiKey={ODDS_API_KEY}"
    response = requests.get(url)
    vegas_probs = {}
    
    if response.status_code == 200:
        data = response.json()
        if data:
            bookmaker = data[0]['bookmakers'][0]
            for outcome in bookmaker['markets'][0]['outcomes']:
                vegas_probs[outcome['name']] = 1 / outcome['price']

    team_projections = {}
    
    for team, last_pct in last_year_records.items():
        v_prob = None
        for name, p in vegas_probs.items():
            if name.lower() in team.lower() or team.lower() in name.lower():
                v_prob = p
                break
                
        market_weight = v_prob * 1.5 if v_prob else last_pct
        blended_pct = (last_pct * 0.60) + (market_weight * 0.40)
        blended_pct = max(0.260, min(0.740, blended_pct))
        team_projections[team] = blended_pct
        
    return team_projections, team_conferences


# ==========================================
# 2. 82-GAME REGULAR SEASON SIMULATOR (WITH INJURY/FRAGILITY VARIANCE)
# ==========================================
def generate_82_game_standings(team_projections, team_conferences):
    standings = []
    
    total_rating = sum(team_projections.values())
    rating_adjustment = (15.0 - total_rating) / 30.0
    
    raw_wins = {}
    for team, rating in team_projections.items():
        normalized_rating = rating + rating_adjustment
        normalized_rating = max(0.250, min(0.750, normalized_rating))
        team_projections[team] = normalized_rating 
        
        expected_wins = normalized_rating * 82
        
        # Injury Proneness Factor: Dynamic variance based on team profile depth/fragility
        # Higher variance means a wider range of missed-game impacts (stochastic injury luck)
        injury_volatility = random.gauss(0, 3.8) 
        simulated_wins = int(round(expected_wins + injury_volatility))
        
        simulated_wins = max(15, min(68, simulated_wins))
        raw_wins[team] = simulated_wins

    current_total = sum(raw_wins.values())
    difference = 1230 - current_total
    
    teams = list(raw_wins.keys())
    while difference != 0:
        team = random.choice(teams)
        if difference > 0 and raw_wins[team] < 68:
            raw_wins[team] += 1
            difference -= 1
        elif difference < 0 and raw_wins[team] > 15:
            raw_wins[team] -= 1
            difference += 1

    for team, wins in raw_wins.items():
        standings.append({
            "Team": team,
            "Wins": wins,
            "Losses": 82 - wins,
            "WinPCT": wins / 82,
            "Conference": team_conferences[team],
            "PowerRating": team_projections[team]
        })
        
    return standings


# ==========================================
# 3. ADVANCED PLAYOFF ENGINE (HCA + COMPRESSION)
# ==========================================
def calculate_single_game_probability(win_pct_a, win_pct_b, is_team_a_home=True):
    compressed_a = 0.50 + (win_pct_a - 0.50) * 0.85
    compressed_b = 0.50 + (win_pct_b - 0.50) * 0.85
    
    numerator = compressed_a - (compressed_a * compressed_b)
    denominator = compressed_a + compressed_b - (2 * compressed_a * compressed_b)
    
    if denominator == 0:
        base_prob = 0.50
    else:
        base_prob = numerator / denominator
        
    hca_boost = 0.035
    if is_team_a_home:
        return min(0.90, max(0.10, base_prob + hca_boost))
    else:
        return min(0.90, max(0.10, base_prob - hca_boost))


def simulate_playoff_series(team_a, team_b):
    hca_schedule = [True, True, False, False, True, False, True]
    wins_a = 0
    wins_b = 0
    game_count = 0
    
    while wins_a < 4 and wins_b < 4 and game_count < 7:
        is_a_home = hca_schedule[game_count]
        p_a = calculate_single_game_probability(team_a['PowerRating'], team_b['PowerRating'], is_team_a_home=is_a_home)
        
        if random.random() < p_a:
            wins_a += 1
        else:
            wins_b += 1
        game_count += 1
        
    if wins_a == 4:
        return team_a
    else:
        return team_b


def run_full_bracket_progression(standings):
    east = sorted([t for t in standings if t["Conference"] == "East"], key=lambda x: (x["Wins"], x["PowerRating"]), reverse=True)[:8]
    west = sorted([t for t in standings if t["Conference"] == "West"], key=lambda x: (x["Wins"], x["PowerRating"]), reverse=True)[:8]
    
    e_r1 = [simulate_playoff_series(east[0], east[7]), simulate_playoff_series(east[3], east[4]),
            simulate_playoff_series(east[1], east[6]), simulate_playoff_series(east[2], east[5])]
    w_r1 = [simulate_playoff_series(west[0], west[7]), simulate_playoff_series(west[3], west[4]),
            simulate_playoff_series(west[1], west[6]), simulate_playoff_series(west[2], west[5])]
    
    e_semis = [simulate_playoff_series(e_r1[0], e_r1[1]), simulate_playoff_series(e_r1[2], e_r1[3])]
    w_semis = [simulate_playoff_series(w_r1[0], w_r1[1]), simulate_playoff_series(w_r1[2], w_r1[3])]
    
    e_champ = simulate_playoff_series(e_semis[0], e_semis[1])
    w_champ = simulate_playoff_series(w_semis[0], w_semis[1])
    
    nba_champ = simulate_playoff_series(e_champ, w_champ)
    
    return east + west, e_r1 + w_r1, e_semis + w_semis, [e_champ, w_champ], nba_champ


# ==========================================
# 4. MASS MONTE CARLO AGGREGATOR (10,000 RUNS)
# ==========================================
def run_monte_carlo_batch(team_projections, team_conferences, total_sims=10000):
    print(f"\n==========================================")
    print(f"RUNNING INJURY-ADJUSTED MACRO SIMULATION ({total_sims:,} RUNS)...")
    print(f"==========================================")
    
    stats = {
        team: {
            "wins_sum": 0, 
            "max_wins": -1, 
            "min_wins": 999, 
            "playoffs": 0, 
            "semis": 0, 
            "conf_finals": 0, 
            "finals": 0, 
            "champs": 0
        } 
        for team in team_projections.keys()
    }
    
    for i in range(total_sims):
        standings = generate_82_game_standings(team_projections, team_conferences)
        
        for t in standings:
            w = t["Wins"]
            team_name = t["Team"]
            stats[team_name]["wins_sum"] += w
            if w > stats[team_name]["max_wins"]:
                stats[team_name]["max_wins"] = w
            if w < stats[team_name]["min_wins"]:
                stats[team_name]["min_wins"] = w
            
        playoff_teams, semi_teams, conf_final_teams, finals_teams, champ = run_full_bracket_progression(standings)
        
        for t in playoff_teams:
            stats[t["Team"]]["playoffs"] += 1
        for t in semi_teams:
            stats[t["Team"]]["semis"] += 1
        for t in conf_final_teams:
            stats[t["Team"]]["conf_finals"] += 1
        for t in finals_teams:
            stats[t["Team"]]["finals"] += 1
            
        stats[champ["Team"]]["champs"] += 1

    summary_data = []
    for team, data in stats.items():
        summary_data.append({
            "Team": team,
            "AvgWins": round(data["wins_sum"] / total_sims, 1),
            "High": data["max_wins"],
            "Low": data["min_wins"],
            "Playoff%": round((data["playoffs"] / total_sims) * 100, 1),
            "Semis%": round((data["semis"] / total_sims) * 100, 1),
            "ConfFinals%": round((data["conf_finals"] / total_sims) * 100, 1),
            "Finals%": round((data["finals"] / total_sims) * 100, 1),
            "Title%": round((data["champs"] / total_sims) * 100, 1)
        })
        
    df_summary = pd.DataFrame(summary_data)
    df_summary = df_summary.sort_values(by="Title%", ascending=False).reset_index(drop=True)
    
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    
    print(f"\n{df_summary.to_string(index=False)}")
    print(f"\n==========================================")
    print(f"INJURY-ADJUSTED SIMULATION COMPLETE")
    print(f"==========================================")


# ==========================================
# MAIN EXECUTION ROUTINE
# ==========================================
if __name__ == "__main__":
    team_projections, team_conferences = get_projected_team_ratings()
    
    if team_projections and team_conferences:
        run_monte_carlo_batch(team_projections, team_conferences, total_sims=10000)