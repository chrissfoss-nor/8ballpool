"""Tests for AI agent"""
import pytest
from src.ai.agent import PoolAI


def test_ai_creation():
    """Test creating AI with different difficulties"""
    ai_easy = PoolAI(difficulty="easy")
    ai_medium = PoolAI(difficulty="medium")
    ai_hard = PoolAI(difficulty="hard")
    
    assert ai_easy.accuracy == 0.5
    assert ai_medium.accuracy == 0.75
    assert ai_hard.accuracy == 0.95


def test_best_shot_calculation():
    """Test AI calculating best shot"""
    ai = PoolAI(difficulty="medium")
    
    cue_ball_pos = (25.0, 25.0)
    target_balls = [
        {"number": 1, "x": 30.0, "y": 25.0},
        {"number": 2, "x": 75.0, "y": 25.0}
    ]
    pocket_positions = [
        (10.0, 10.0),
        (50.0, 10.0),
        (90.0, 10.0)
    ]
    
    shot = ai.calculate_best_shot(cue_ball_pos, target_balls, pocket_positions)
    
    assert "angle" in shot
    assert "power" in shot
    assert 0.0 <= shot["power"] <= 1.0


def test_empty_target_balls():
    """Test AI behavior with no target balls"""
    ai = PoolAI(difficulty="medium")
    
    shot = ai.calculate_best_shot((25.0, 25.0), [], [(10.0, 10.0)])
    
    assert shot["angle"] == 0
    assert shot["power"] == 0.5
