"""Tests for physics engine"""
import pytest
from src.game.physics import Ball, PhysicsEngine


def test_ball_creation():
    """Test creating a ball"""
    ball = Ball(number=1, x=10.0, y=20.0)
    assert ball.number == 1
    assert ball.x == 10.0
    assert ball.y == 20.0
    assert ball.vx == 0.0
    assert ball.vy == 0.0
    assert not ball.is_pocketed


def test_ball_movement():
    """Test ball movement with velocity"""
    ball = Ball(number=1, x=10.0, y=10.0)
    ball.vx = 5.0
    ball.vy = 3.0
    
    ball.update_position(dt=1.0)
    
    assert ball.x == 15.0  # 10 + 5*1
    assert ball.y == 13.0  # 10 + 3*1


def test_collision_detection():
    """Test collision detection between balls"""
    engine = PhysicsEngine()
    
    ball1 = Ball(number=1, x=10.0, y=10.0)
    ball2 = Ball(number=2, x=10.5, y=10.0)  # Close to ball1
    ball3 = Ball(number=3, x=50.0, y=50.0)  # Far from ball1
    
    assert engine.check_collision(ball1, ball2)
    assert not engine.check_collision(ball1, ball3)


def test_wall_collision():
    """Test ball collision with walls"""
    engine = PhysicsEngine(table_width=100, table_height=50)
    
    # Ball going left
    ball = Ball(number=1, x=0.3, y=25.0)
    ball.vx = -5.0
    
    engine.check_wall_collision(ball)
    
    # Velocity should be reversed (bounced)
    assert ball.vx > 0
    assert ball.x >= ball.radius
