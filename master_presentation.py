from manim import *
import numpy as np

class PrivaseeeFullStory(Scene):
    def construct(self):
        # --- INTRODUCTION: THE PERSONAL WHY ---
        intro_text = Text("Privacy is a Human Right", color=WHITE).scale(0.8)
        self.play(Write(intro_text))
        self.wait(1)
        self.play(intro_text.animate.to_edge(UP))

        mission_sub = Text("Built to end Cyber-Harassment", color=YELLOW, font_size=24).next_to(intro_text, DOWN)
        self.play(FadeIn(mission_sub))
        self.wait(2)
        self.play(FadeOut(intro_text), FadeOut(mission_sub))

        # --- SCENE 1: THE CRISIS (PAIN POINTS) ---
        problem_title = Text("The Provenance Crisis", color=RED).to_edge(UP)
        self.play(Write(problem_title))

        image_box = Square(side_length=3, fill_opacity=0.2, color=BLUE)
        image_label = Text("Original Content", font_size=24).next_to(image_box, DOWN)
        self.play(Create(image_box), Write(image_label))

        # Show traditional watermark being deleted
        wm_text = Text("Fragile Metadata/LSB", color=RED, font_size=20).move_to(image_box.get_center())
        self.play(Write(wm_text))
        
        # The Attack
        self.play(image_box.animate.scale(0.6).set_color(RED)) # Crop simulation
        self.play(FadeOut(wm_text))
        
        caption = Text("Attribution Lost. Identity Erased.", color=RED, font_size=24).next_to(image_box, UP)
        self.play(Write(caption))
        self.wait(2)
        self.play(FadeOut(image_box), FadeOut(image_label), FadeOut(caption), FadeOut(problem_title))

        # --- SCENE 2: THE TECH (DWT FREQUENCIES) ---
        tech_title = Text("The Solution: Frequency-Domain Embedding", color=GREEN).scale(0.7).to_edge(UP)
        self.play(Write(tech_title))

        wave_1 = FunctionGraph(lambda x: np.sin(x), x_range=[-3, 3], color=BLUE)
        wave_2 = FunctionGraph(lambda x: np.sin(3*x) * 0.4, x_range=[-3, 3], color=PURPLE)
        waves = VGroup(wave_1, wave_2).arrange(DOWN)
        self.play(Create(waves))

        data_packet = Square(side_length=0.4, fill_opacity=1, color=YELLOW).move_to(LEFT*4)
        self.play(data_packet.animate.move_to(waves.get_center()))
        self.play(waves.animate.set_color(YELLOW), FadeOut(data_packet))

        dwt_label = Text("DWT survives Cropping & Compression", font_size=24).next_to(waves, DOWN)
        self.play(Write(dwt_label))
        self.wait(2)
        self.play(FadeOut(waves), FadeOut(dwt_label), FadeOut(tech_title))

        # --- SCENE 3: THE AI (DINOV2 + CLIP) ---
        ai_title = Text("AI Awareness: Surviving the Analog Hole", color=PURPLE).scale(0.7).to_edge(UP)
        self.play(Write(ai_title))

        distorted = Square(side_length=2, color=RED).rotate(PI/6).set_opacity(0.3)
        dist_label = Text("Phone Photo of Screen", font_size=20).next_to(distorted, DOWN)
        
        brain = Circle(radius=1.2, color=WHITE).to_edge(RIGHT)
        brain_label = Text("DinoV2", font_size=24).move_to(brain.get_center())
        
        self.play(Create(distorted), Write(dist_label), Create(brain), Write(brain_label))
        self.play(Arrow(distorted.get_right(), brain.get_left()).animate)
        
        success = Text("IDENTITY VERIFIED (99%)", color=GREEN, font_size=30).next_to(brain, UP)
        self.play(Write(success))
        self.wait(2)
        self.play(FadeOut(distorted), FadeOut(dist_label), FadeOut(brain), FadeOut(brain_label), FadeOut(success), FadeOut(ai_title))

        # --- SCENE 4: BLOCKCHAIN & ACCOUNTABILITY ---
        bc_title = Text("Immutable Proof of Origin", color=BLUE).scale(0.7).to_edge(UP)
        self.play(Write(bc_title))

        blocks = VGroup(*[Square(side_length=1) for _ in range(3)]).arrange(RIGHT, buff=0.5)
        chain = VGroup(*[Line(blocks[i].get_right(), blocks[i+1].get_left()) for i in range(2)])
        self.play(Create(blocks), Create(chain))
        
        self.play(Write(Text("0xHASH", font_size=18).move_to(blocks[1].get_center())))
        desc = Text("Evidence that cannot be deleted.", font_size=24).next_to(blocks, DOWN)
        self.play(Write(desc))
        self.wait(2)
        self.play(FadeOut(blocks), FadeOut(chain), FadeOut(desc), FadeOut(bc_title))

        # --- FINAL MISSION: EMPOWERMENT ---
        final_msg = Text("Privaseee: A Weapon for Digital Self-Defense", color=WHITE).scale(0.7)
        self.play(Write(final_msg))
        
        github = Text("github.com/your-username/privaseee", color=BLUE, font_size=24).next_to(final_msg, DOWN)
        self.play(FadeIn(github))
        
        self.wait(3)
        self.play(FadeOut(final_msg), FadeOut(github))
