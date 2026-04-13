import pygame
import time
import csv
import random
import math

# --- Configuration & Aesthetics ---
WHITE = (255, 255, 255)
DARK_BG = (20, 24, 35)      # Modern dark theme
NEON_BLUE = (0, 255, 240)   # UI Accents
NEON_PINK = (255, 0, 127)   # Target color
GREEN = (50, 255, 50)

# --- Initialization ---
pygame.init()
SCREEN_WIDTH, SCREEN_HEIGHT = 1000, 700
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Neuro-Osu: Adaptive Kinetic Path-Finder")
clock = pygame.time.Clock()
font_main = pygame.font.SysFont("Arial", 24, bold=True)

# --- Data Logging Setup [cite: 19, 25] ---
csv_file = open('patient_data.csv', 'w', newline='')
data_writer = csv.writer(csv_file)
data_writer.writerow(['Timestamp', 'Reaction_Time', 'Error_Distance', 'Current_Difficulty'])

class Target:
    def __init__(self, difficulty):
        # Difficulty adjusts the radius (smaller = harder) 
        self.radius = max(15, 50 - (difficulty * 5))
        self.x = random.randint(100, SCREEN_WIDTH - 100)
        self.y = random.randint(100, SCREEN_HEIGHT - 100)
        self.spawn_time = time.time()
        self.hit = False

    def draw(self, surface):
        # "Osu-style" approach circle for reaction-time assessment
        elapsed = (time.time() - self.spawn_time) * 2.0
        approach_radius = max(self.radius, 100 - (elapsed * 50))
        
        pygame.draw.circle(surface, NEON_BLUE, (self.x, self.y), int(approach_radius), 2)
        pygame.draw.circle(surface, NEON_PINK, (self.x, self.y), self.radius)

def run_game():
    difficulty = 1  # Starting level
    score = 0
    running = True
    current_target = Target(difficulty)
    performance_history = [] # To calculate "Stability Ratio" 

    while running:
        screen.fill(DARK_BG)
        mouse_pos = pygame.mouse.get_pos()
        
        # UI Overlay 
        score_text = font_main.render(f"Neural Stability Score: {score}", True, WHITE)
        diff_text = font_main.render(f"System Load (Difficulty): {difficulty}", True, NEON_BLUE)
        screen.blit(score_text, (20, 20))
        screen.blit(diff_text, (20, 50))

        # Event Handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                # Calculate Reaction Time and Accuracy
                dist = math.hypot(mouse_pos[0] - current_target.x, mouse_pos[1] - current_target.y)
                
                if dist <= current_target.radius:
                    reaction_time = time.time() - current_target.spawn_time
                    error_dist = dist
                    
                    # Log Data 
                    data_writer.writerow([time.time(), reaction_time, error_dist, difficulty])
                    performance_history.append(reaction_time)
                    
                    # Adaptive Difficulty Logic 
                    # If patient is fast and stable, increase difficulty
                    if len(performance_history) > 5:
                        avg_rt = sum(performance_history[-5:]) / 5
                        if avg_rt < 0.8: # Threshold for "Improvement"
                            difficulty += 1
                            performance_history = [] # Reset for next tier
                    
                    score += 100
                    current_target = Target(difficulty)

        # Draw mechanics
        current_target.draw(screen)
        
        # Real-time visual feedback: Cursor line (Motion tracking) [cite: 18]
        pygame.draw.line(screen, (50, 50, 50), (current_target.x, current_target.y), mouse_pos, 1)

        pygame.display.flip()
        clock.tick(60)

    csv_file.close()
    pygame.quit()

if __name__ == "__main__":
    run_game()