import pygame
import face_recognition
import cv2
import numpy as np
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime


class ModernAttendanceSystem:
    def __init__(self):
        # Initialize Pygame
        pygame.init()

        # Screen setup
        self.SCREEN_WIDTH = 1200
        self.SCREEN_HEIGHT = 800
        self.screen = pygame.display.set_mode((self.SCREEN_WIDTH, self.SCREEN_HEIGHT))
        pygame.display.set_caption("Modern Attendance System")

        # Colors
        self.COLORS = {
            'background': (18, 18, 18),
            'primary': (79, 70, 229),
            'secondary': (45, 45, 45),
            'text': (255, 255, 255),
            'text_dim': (128, 128, 128),
            'success': (34, 197, 94),
            'error': (239, 68, 68),
            'absent': (239, 68, 68),
            'present': (34, 197, 94),
            'button': (59, 130, 246),
            'button_hover': (37, 99, 235)
        }

        # Fonts
        self.fonts = {
            'title': pygame.font.Font(None, 56),
            'large': pygame.font.Font(None, 48),
            'medium': pygame.font.Font(None, 36),
            'small': pygame.font.Font(None, 24)
        }

        # UI Elements
        self.input_rect = pygame.Rect(50, 100, 300, 50)
        self.buttons = {
            'face_recognition': pygame.Rect(50, 170, 300, 50),
            'refresh': pygame.Rect(50, 240, 300, 50),
            'manual_entry': pygame.Rect(50, 310, 300, 50)
        }

        # UI State
        self.active_input = False
        self.input_text = ""
        self.message = {'text': '', 'color': self.COLORS['text'], 'timer': 0}
        self.scroll_offset = 0
        self.face_recognition_active = False
        self.hover_button = None

        # Initialize core systems
        try:
            self.setup_google_sheets()
            self.setup_student_data()
            self.setup_face_recognition()
        except Exception as e:
            self.show_message(f"Initialization error: {str(e)}", self.COLORS['error'])

    def show_message(self, text, color):
        """Display a message with a specified color for 3 seconds"""
        self.message = {
            'text': text,
            'color': color,
            'timer': 180  # 3 seconds at 60 FPS
        }
        print(text)  # Also print to console for debugging

    def validate_prn(self, prn):
        """Validate PRN format"""
        try:
            prn = str(prn).strip()
            # Check for alphanumeric characters only
            if not prn.isalnum():
                self.show_message("PRN must be alphanumeric characters", self.COLORS['error'])
                return None
            if prn not in self.students_data:
                self.show_message(f"PRN {prn} not found in the database", self.COLORS['error'])
                return None
            return prn
        except Exception as e:
            self.show_message(f"PRN validation error: {str(e)}", self.COLORS['error'])
            return None

    def is_lecture_time(self):
        """Check if current time is within any lecture slot"""
        current_lecture = self.get_current_lecture()
        if not current_lecture:
            self.show_message("No active lecture at this time", self.COLORS['error'])
            return False
        return True

    def cleanup(self):
        """Clean up resources before closing"""
        try:
            if hasattr(self, 'cap') and self.cap is not None:
                self.cap.release()
            pygame.quit()
        except Exception as e:
            print(f"Cleanup error: {str(e)}")

    def setup_google_sheets(self):
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive"
        ]
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                'pathtoyourcredentials.json', scope)
            client = gspread.authorize(creds)
            self.sheet = client.open('sheet_name').sheet1
            self.show_message("Connected to Google Sheets", self.COLORS['success'])
        except Exception as e:
            self.show_message(f"Google Sheets connection failed: {str(e)}", self.COLORS['error'])
            raise

    def setup_student_data(self):
        try:
            self.students_data = {}
            records = self.sheet.get_all_records()
            for record in records:
                prn = str(record['PRN'])  # Convert to string to handle numeric PRNs
                name = record['RName']
                self.students_data[prn] = {
                    'name': name,
                    'attendance': {f'Lecture{i}': 'Absent' for i in range(1, 9)}
                }

            # Update local attendance data from sheet
            self.update_attendance_from_sheet()

        except Exception as e:
            self.show_message(f"Error loading student data: {str(e)}", self.COLORS['error'])
            raise

    def update_attendance_from_sheet(self):
        """Update local attendance data from Google Sheet"""
        try:
            all_values = self.sheet.get_all_records()
            self.students_data = {}
            for record in all_values:
                prn = str(record['PRN'])
                name = record['RName']
                self.students_data[prn] = {
                    'name': name,
                    'attendance': {f'Lecture{i}': record.get(f'Lecture{i}', 'Absent') for i in range(1, 9)}
                }
            self.show_message("Data refreshed successfully", self.COLORS['success'])
        except Exception as e:
            self.show_message(f"Error refreshing data: {str(e)}", self.COLORS['error'])

    def setup_face_recognition(self):
        self.face_encodings = {}
        self.path = 'images'
        if not os.path.exists(self.path):
            os.makedirs(self.path)

        try:
            for image_file in os.listdir(self.path):
                if image_file.endswith(('.jpg', '.jpeg', '.png')):
                    prn = image_file.split('.')[0]
                    image_path = os.path.join(self.path, image_file)
                    self.add_face_encoding(prn, image_path)
        except Exception as e:
            self.show_message(f"Face recognition setup error: {str(e)}", self.COLORS['error'])

    def add_face_encoding(self, prn, image_path):
        try:
            image = face_recognition.load_image_file(image_path)
            encoding = face_recognition.face_encodings(image)[0]
            self.face_encodings[prn] = encoding
            return True
        except Exception as e:
            self.show_message(f"Error encoding face for PRN {prn}: {str(e)}", self.COLORS['error'])
            return False

    def get_current_lecture(self):
        lectures = {
            "Lecture1": ("08:00", "09:00"),
            "Lecture2": ("09:10", "10:10"),
            "Lecture3": ("10:20", "11:20"),
            "Lecture4": ("11:30", "12:30"),
            "Lecture5": ("14:00", "15:00"),
            "Lecture6": ("15:10", "16:10"),
            "Lecture7": ("16:20", "17:20"),
            "Lecture8": ("17:30", "23:30")
        }

        now = datetime.now().strftime("%H:%M")
        for lecture, (start, end) in lectures.items():
            if start <= now <= end:
                return lecture
        return None

    def mark_attendance(self, prn):
        current_lecture = self.get_current_lecture()
        if not current_lecture:
            self.show_message("No active lecture at this time", self.COLORS['error'])
            return False

        prn = str(prn).strip()  # Clean the PRN
        if not prn:
            self.show_message("Please enter a valid PRN", self.COLORS['error'])
            return False

        if prn not in self.students_data:
            self.show_message(f"PRN {prn} not found", self.COLORS['error'])
            return False

        student = self.students_data[prn]
        if student['attendance'][current_lecture] == 'Present':
            self.show_message(f"Already marked present: {student['name']}", self.COLORS['error'])
            return False

        try:
            # Find PRN in sheet
            cell = self.sheet.find(prn)
            if cell:
                row_num = cell.row
                col_num = self.sheet.find(current_lecture).col

                # Update Google Sheet
                self.sheet.update_cell(row_num, col_num, 'Present')

                # Update local data
                student['attendance'][current_lecture] = 'Present'
                self.show_message(f"Marked present: {student['name']}", self.COLORS['success'])
                return True
            else:
                self.show_message("Error: PRN not found in sheet", self.COLORS['error'])
                return False

        except Exception as e:
            self.show_message(f"Error marking attendance: {str(e)}", self.COLORS['error'])
            return False

    def handle_manual_entry(self):
        """Process manual PRN entry"""
        if not self.input_text:
            self.show_message("Please enter a PRN", self.COLORS['error'])
            return

        prn = self.validate_prn(self.input_text)
        if prn:
            self.mark_attendance(prn)
            self.input_text = ""  # Clear input after successful marking

    def process_face_recognition(self):
        if not self.face_recognition_active:
            return

        try:
            ret, frame = self.cap.read()
            if ret:
                # Convert the frame from BGR to RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Resize frame for faster face recognition
                small_frame = cv2.resize(rgb_frame, (0, 0), fx=0.25, fy=0.25)

                # Find all faces in the frame
                face_locations = face_recognition.face_locations(small_frame)
                face_encodings = face_recognition.face_encodings(small_frame, face_locations)

                # Check each face against known faces
                for face_encoding in face_encodings:
                    matches = []
                    for prn, known_encoding in self.face_encodings.items():
                        match = face_recognition.compare_faces([known_encoding], face_encoding, tolerance=0.6)[0]
                        if match:
                            matches.append(prn)

                    # Mark attendance for matched faces
                    if matches:
                        for prn in matches:
                            self.mark_attendance(prn)

                # Display the camera feed
                frame = cv2.flip(frame, 1)  # Mirror the feed
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                surface = pygame.surfarray.make_surface(np.rot90(rgb_frame))
                scaled_surface = pygame.transform.scale(surface, (400, 300))
                self.screen.blit(scaled_surface, (self.SCREEN_WIDTH - 420, 20))

        except Exception as e:
            self.show_message(f"Face recognition error: {str(e)}", self.COLORS['error'])
            self.toggle_face_recognition()  # Turn off face recognition on error

    def toggle_face_recognition(self):
        if not self.face_recognition_active:
            if len(self.face_encodings) == 0:
                self.show_message("No face recognition data available", self.COLORS['error'])
                return
            try:
                self.cap = cv2.VideoCapture(0)

                if not self.cap.isOpened():
                    raise Exception("Could not open camera")
                self.face_recognition_active = True
                self.show_message("Face recognition activated", self.COLORS['success'])
            except Exception as e:
                self.show_message(f"Camera error: {str(e)}", self.COLORS['error'])
        else:
            self.cap.release()
            self.face_recognition_active = False
            self.show_message("Face recognition deactivated", self.COLORS['text'])

    def update_screen_size(self):
        """Update screen size and related UI elements"""
        info = pygame.display.Info()
        self.SCREEN_WIDTH = min(1200, info.current_w)
        self.SCREEN_HEIGHT = min(800, info.current_h)
        self.screen = pygame.display.set_mode((self.SCREEN_WIDTH, self.SCREEN_HEIGHT))

        # Update UI element positions
        self.input_rect = pygame.Rect(50, 100, 300, 50)
        self.buttons = {
            'face_recognition': pygame.Rect(50, 170, 300, 50),
            'refresh': pygame.Rect(50, 240, 300, 50),
            'manual_entry': pygame.Rect(50, 310, 300, 50)
        }

    def handle_resize(self, event):
        """Handle window resize events"""
        if event.type == pygame.VIDEORESIZE:
            self.update_screen_size()

    def draw_ui(self):
        # Draw title
        title = self.fonts['title'].render("Attendance System", True, self.COLORS['text'])
        self.screen.blit(title, (50, 30))

        # Draw input box
        pygame.draw.rect(self.screen,
                         self.COLORS['primary'] if self.active_input else self.COLORS['secondary'],
                         self.input_rect, border_radius=5)

        if self.input_text:
            text_surface = self.fonts['medium'].render(self.input_text, True, self.COLORS['text'])
        else:
            text_surface = self.fonts['medium'].render("Enter PRN...", True, self.COLORS['text_dim'])
        text_rect = text_surface.get_rect(midleft=(self.input_rect.x + 10, self.input_rect.centery))
        self.screen.blit(text_surface, text_rect)

        # Draw buttons
        button_texts = {
            'face_recognition': 'Face Recognition',
            'refresh': 'Refresh Data',
            'manual_entry': 'Manual Entry'
        }

        for name, rect in self.buttons.items():
            color = self.COLORS['button_hover'] if name == self.hover_button else self.COLORS['button']
            pygame.draw.rect(self.screen, color, rect, border_radius=5)
            text = self.fonts['medium'].render(button_texts[name], True, self.COLORS['text'])
            text_rect = text.get_rect(center=rect.center)
            self.screen.blit(text, text_rect)

            # Draw message
        if self.message['timer'] > 0:
            message_surface = self.fonts['medium'].render(self.message['text'], True, self.message['color'])
            message_rect = message_surface.get_rect(midleft=(50, 380))
            self.screen.blit(message_surface, message_rect)
            self.message['timer'] -= 1

            # Draw attendance list
        self.draw_attendance_list()

    def draw_attendance_list(self):
        """Draw the scrollable attendance list"""
        # List background
        list_rect = pygame.Rect(50, 420, self.SCREEN_WIDTH - 100, self.SCREEN_HEIGHT - 470)
        pygame.draw.rect(self.screen, self.COLORS['secondary'], list_rect, border_radius=5)

        # Headers
        headers = ['PRN', 'Name', 'Current Lecture', 'Status']
        header_widths = [150, 200, 220, 120]  # Increased widths for columns
        x_pos = list_rect.x + 20
        for header, width in zip(headers, header_widths):
            header_surface = self.fonts['medium'].render(header, True, self.COLORS['text'])
            self.screen.blit(header_surface, (x_pos, list_rect.y + 10))
            x_pos += width

        # Student entries
        current_lecture = self.get_current_lecture() or "No Active Lecture"
        y_pos = list_rect.y + 50 + self.scroll_offset
        line_height = 40

        for prn, data in self.students_data.items():
            if y_pos + line_height > list_rect.y and y_pos < list_rect.bottom:
                x_pos = list_rect.x + 20

                # PRN
                prn_surface = self.fonts['small'].render(prn, True, self.COLORS['text'])
                self.screen.blit(prn_surface, (x_pos, y_pos))
                x_pos += header_widths[0]

                # Name
                name_surface = self.fonts['small'].render(data['name'], True, self.COLORS['text'])
                self.screen.blit(name_surface, (x_pos, y_pos))
                x_pos += header_widths[1]

                # Current Lecture
                lecture_surface = self.fonts['small'].render(current_lecture, True, self.COLORS['text'])
                self.screen.blit(lecture_surface, (x_pos, y_pos))
                x_pos += header_widths[2]

                # Status
                status = data['attendance'].get(current_lecture, 'Absent')
                status_color = self.COLORS['present'] if status == 'Present' else self.COLORS['absent']
                status_surface = self.fonts['small'].render(status, True, status_color)
                self.screen.blit(status_surface, (x_pos, y_pos))

            y_pos += line_height

    def run(self):
        """Main application loop"""
        clock = pygame.time.Clock()
        running = True

        while running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mouse_pos = pygame.mouse.get_pos()

                    # Handle input box click
                    if self.input_rect.collidepoint(mouse_pos):
                        self.active_input = not self.active_input
                    else:
                        self.active_input = False

                    # Handle button clicks
                    for name, rect in self.buttons.items():
                        if rect.collidepoint(mouse_pos):
                            if name == 'face_recognition':
                                self.toggle_face_recognition()
                            elif name == 'refresh':
                                self.update_attendance_from_sheet()
                            elif name == 'manual_entry':
                                self.handle_manual_entry()

                    # Handle scrolling
                    if event.button in (4, 5):  # Mouse wheel up (4) or down (5)
                        self.scroll_offset += 30 if event.button == 4 else -30
                        max_scroll = -len(self.students_data) * 40 + self.SCREEN_HEIGHT - 470
                        self.scroll_offset = min(0, max(max_scroll, self.scroll_offset))

                elif event.type == pygame.KEYDOWN:
                    if self.active_input:
                        if event.key == pygame.K_RETURN:
                            self.handle_manual_entry()
                        elif event.key == pygame.K_BACKSPACE:
                            self.input_text = self.input_text[:-1]
                        else:
                            if len(self.input_text) < 12:  # Limit input length
                                self.input_text += event.unicode

                elif event.type == pygame.MOUSEMOTION:
                    # Handle button hover effects
                    mouse_pos = pygame.mouse.get_pos()
                    self.hover_button = None
                    for name, rect in self.buttons.items():
                        if rect.collidepoint(mouse_pos):
                            self.hover_button = name
                            break

            # Update screen
            self.screen.fill(self.COLORS['background'])
            if self.face_recognition_active:
                self.process_face_recognition()
            self.draw_ui()
            pygame.display.flip()
            clock.tick(60)

        # Perform cleanup after the loop ends
        self.cleanup()


if __name__ == "__main__":
    attendance_system = ModernAttendanceSystem()
    attendance_system.run()
