"""Physics engine for ball collisions and movement"""
import numpy as np
from typing import List, Tuple, Dict


class Ball:
    """Represents a pool ball"""
    def __init__(self, number: int, x: float, y: float, radius: float = 0.5):
        self.number = number
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.radius = radius
        self.is_pocketed = False
    
    def update_position(self, dt: float):
        """Update ball position based on velocity"""
        self.x += self.vx * dt
        self.y += self.vy * dt
        
        # Apply friction
        friction = 0.98
        self.vx *= friction
        self.vy *= friction
        
        # Stop if velocity is very small
        if abs(self.vx) < 0.01 and abs(self.vy) < 0.01:
            self.vx = 0
            self.vy = 0


class PhysicsEngine:
    """Handles physics calculations for the pool game"""
    
    def __init__(self, table_width: float = 100, table_height: float = 50):
        self.table_width = table_width
        self.table_height = table_height
        self.ball_radius = 0.5
        
    def check_collision(self, ball1: Ball, ball2: Ball) -> bool:
        """Check if two balls collide"""
        dx = ball2.x - ball1.x
        dy = ball2.y - ball1.y
        distance = np.sqrt(dx**2 + dy**2)
        return distance < (ball1.radius + ball2.radius)
    
    def resolve_collision(self, ball1: Ball, ball2: Ball):
        """Resolve collision between two balls"""
        dx = ball2.x - ball1.x
        dy = ball2.y - ball1.y
        distance = np.sqrt(dx**2 + dy**2)
        
        if distance == 0:
            return
        
        # Normalize
        nx = dx / distance
        ny = dy / distance
        
        # Relative velocity
        dvx = ball1.vx - ball2.vx
        dvy = ball1.vy - ball2.vy
        
        # Relative velocity in collision normal direction
        dvn = dvx * nx + dvy * ny
        
        # Do not resolve if velocities are separating
        if dvn > 0:
            return
        
        # Collision impulse
        impulse = 2 * dvn / 2  # Assuming equal mass
        
        # Apply impulse
        ball1.vx -= impulse * nx
        ball1.vy -= impulse * ny
        ball2.vx += impulse * nx
        ball2.vy += impulse * ny
    
    def check_wall_collision(self, ball: Ball):
        """Check and resolve wall collisions"""
        # Left and right walls
        if ball.x - ball.radius < 0:
            ball.x = ball.radius
            ball.vx = -ball.vx * 0.9
        elif ball.x + ball.radius > self.table_width:
            ball.x = self.table_width - ball.radius
            ball.vx = -ball.vx * 0.9
        
        # Top and bottom walls
        if ball.y - ball.radius < 0:
            ball.y = ball.radius
            ball.vy = -ball.vy * 0.9
        elif ball.y + ball.radius > self.table_height:
            ball.y = self.table_height - ball.radius
            ball.vy = -ball.vy * 0.9
    
    def simulate_step(self, balls: List[Ball], dt: float = 0.016):
        """Simulate one physics step"""
        # Update positions
        for ball in balls:
            if not ball.is_pocketed:
                ball.update_position(dt)
                self.check_wall_collision(ball)
        
        # Check collisions between balls
        active_balls = [b for b in balls if not b.is_pocketed]
        for i in range(len(active_balls)):
            for j in range(i + 1, len(active_balls)):
                if self.check_collision(active_balls[i], active_balls[j]):
                    self.resolve_collision(active_balls[i], active_balls[j])
