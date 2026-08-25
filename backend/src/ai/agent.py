"""AI Agent for playing 8 ball pool"""
import numpy as np
from typing import List, Tuple, Dict


class PoolAI:
    """AI agent for 8 ball pool"""
    
    def __init__(self, difficulty: str = "medium"):
        """
        Initialize AI agent
        
        Args:
            difficulty: "easy", "medium", or "hard"
        """
        self.difficulty = difficulty
        self.skill_levels = {
            "easy": 0.5,
            "medium": 0.75,
            "hard": 0.95
        }
        self.accuracy = self.skill_levels.get(difficulty, 0.75)
    
    def calculate_best_shot(
        self, 
        cue_ball_pos: Tuple[float, float],
        target_balls: List[Dict],
        pocket_positions: List[Tuple[float, float]]
    ) -> Dict[str, float]:
        """
        Calculate the best shot for AI
        
        Args:
            cue_ball_pos: (x, y) position of cue ball
            target_balls: List of target ball positions and numbers
            pocket_positions: List of pocket positions
            
        Returns:
            Dict with 'angle' (degrees) and 'power' (0-1)
        """
        if not target_balls:
            return {"angle": 0, "power": 0.5}
        
        best_shot = None
        best_score = -float('inf')
        
        # Evaluate each target ball
        for target in target_balls:
            target_pos = (target['x'], target['y'])
            
            # Find closest pocket
            closest_pocket = min(
                pocket_positions,
                key=lambda p: self._distance(target_pos, p)
            )
            
            # Calculate shot angle and power
            angle = self._calculate_angle(cue_ball_pos, target_pos)
            power = self._calculate_power(cue_ball_pos, target_pos)
            
            # Calculate shot difficulty
            difficulty = self._calculate_difficulty(
                cue_ball_pos, 
                target_pos, 
                closest_pocket
            )
            
            # Score this shot
            score = 1.0 / (1.0 + difficulty)
            
            if score > best_score:
                best_score = score
                best_shot = {
                    "angle": angle,
                    "power": min(power, 1.0),
                    "target_ball": target['number']
                }
        
        # Add some randomness based on difficulty
        if best_shot:
            noise = (1 - self.accuracy) * 20  # degrees
            best_shot["angle"] += np.random.uniform(-noise, noise)
            best_shot["power"] += np.random.uniform(-0.1, 0.1) * (1 - self.accuracy)
            best_shot["power"] = np.clip(best_shot["power"], 0.1, 1.0)
        
        return best_shot or {"angle": 0, "power": 0.5}
    
    def _distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        """Calculate Euclidean distance between two points"""
        return np.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
    
    def _calculate_angle(
        self, 
        from_pos: Tuple[float, float], 
        to_pos: Tuple[float, float]
    ) -> float:
        """Calculate angle from one position to another in degrees"""
        dx = to_pos[0] - from_pos[0]
        dy = to_pos[1] - from_pos[1]
        return np.degrees(np.arctan2(dy, dx))
    
    def _calculate_power(
        self, 
        cue_pos: Tuple[float, float], 
        target_pos: Tuple[float, float]
    ) -> float:
        """Calculate required power for a shot (0-1)"""
        distance = self._distance(cue_pos, target_pos)
        # Normalize distance to power (assuming max distance ~100 units)
        power = min(distance / 50.0, 1.0)
        return max(power, 0.3)  # Minimum power
    
    def _calculate_difficulty(
        self,
        cue_pos: Tuple[float, float],
        target_pos: Tuple[float, float],
        pocket_pos: Tuple[float, float]
    ) -> float:
        """
        Calculate shot difficulty score
        Lower is easier
        """
        # Distance from cue to target
        cue_to_target = self._distance(cue_pos, target_pos)
        
        # Distance from target to pocket
        target_to_pocket = self._distance(target_pos, pocket_pos)
        
        # Calculate angle difficulty
        cue_angle = self._calculate_angle(cue_pos, target_pos)
        target_angle = self._calculate_angle(target_pos, pocket_pos)
        angle_diff = abs(cue_angle - target_angle)
        
        # Normalize angle difference (0-180 degrees)
        angle_difficulty = min(angle_diff, 360 - angle_diff) / 180.0
        
        # Combined difficulty
        difficulty = (
            cue_to_target * 0.3 + 
            target_to_pocket * 0.3 + 
            angle_difficulty * 50 * 0.4
        )
        
        return difficulty
