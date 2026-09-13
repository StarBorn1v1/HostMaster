import logging
import sys
import psutil
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMessageBox, QStackedWidget, QWidget

from lattice_view import LatticeGraphicsView
from models import ServerNode, SystemStats, clean_process_name
from scanner import PortScannerWorker
from sidebar import Sidebar
from table_view import AlternativeTableView
from theme import theme_manager, ThemeMode, ColorTokens

logger = logging.getLogger(__name__)

from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from theme import font_heading, font_body, font_mono

class TerminateDialog(QDialog):
    def __init__(self, node_name: str, port: int, pid: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Terminate Process")
        self.setModal(True)
        self.setMinimumWidth(380)
        
        t = theme_manager.tokens
        
        self.setStyleSheet(f"""
            QDialog {{ background-color: {t.hex(t.bg_raised)}; }}
            QLabel#Title {{ color: {t.hex(t.text_max)}; font-size: 16px; font-weight: bold; }}
            QLabel#Subtitle {{ color: {t.hex(t.text_primary)}; font-size: 14px; }}
            QLabel#Disclaimer {{ color: {t.hex(t.text_secondary)}; font-size: 12px; }}
            QPushButton {{ padding: 8px 16px; border-radius: 6px; font-weight: bold; }}
            QPushButton#Cancel {{ background-color: {t.hex(t.bg_control)}; color: {t.hex(t.text_primary)}; }}
            QPushButton#Terminate {{ background-color: {t.hex(t.destructive)}; color: white; border: none; }}
            QPushButton#Terminate:hover {{ background-color: {t.hex(t.destructive_dim)}; }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        title = QLabel(f"Terminate {node_name}?")
        title.setObjectName("Title")
        title.setFont(font_heading())
        
        subtitle = QLabel(f"Port {port}  •  PID {pid}")
        subtitle.setObjectName("Subtitle")
        subtitle.setFont(font_mono())
        
        disclaimer = QLabel("The process will receive SIGTERM. If it does not exit within 1.5s, a SIGKILL will be sent.")
        disclaimer.setObjectName("Disclaimer")
        disclaimer.setWordWrap(True)
        disclaimer.setFont(font_body())
        
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(disclaimer)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        term_btn = QPushButton("Terminate")
        term_btn.setObjectName("Terminate")
        term_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(term_btn)
        
        layout.addLayout(btn_layout)

import subprocess
from PySide6.QtWidgets import QLineEdit

class SudoDialog(QDialog):
    def __init__(self, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Authentication Required")
        self.setModal(True)
        self.setMinimumWidth(380)
        
        t = theme_manager.tokens
        
        self.setStyleSheet(f"""
            QDialog {{ background-color: {t.hex(t.bg_raised)}; }}
            QLabel#Title {{ color: {t.hex(t.text_max)}; font-size: 16px; font-weight: bold; }}
            QLabel#Disclaimer {{ color: {t.hex(t.text_secondary)}; font-size: 13px; }}
            QLineEdit {{
                background-color: {t.hex(t.bg_control)};
                color: {t.hex(t.text_primary)};
                border: 1px solid {t.hex(t.border_hairline)};
                border-radius: 4px;
                padding: 8px;
            }}
            QLineEdit:focus {{ border: 1px solid {t.hex(t.border_focus)}; }}
            QPushButton {{ padding: 8px 16px; border-radius: 6px; font-weight: bold; }}
            QPushButton#Cancel {{ background-color: {t.hex(t.bg_control)}; color: {t.hex(t.text_primary)}; }}
            QPushButton#Submit {{ background-color: {t.hex(t.accent_solid)}; color: white; border: none; }}
            QPushButton#Submit:hover {{ background-color: {t.hex(t.accent_dim)}; }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        title = QLabel("Elevated Privileges Required")
        title.setObjectName("Title")
        title.setFont(font_heading())
        
        disclaimer = QLabel(message + "\n\nEnter your password to execute this command via sudo.\n\n🛡️ Your password is used exactly once, piped directly to the system, and instantly discarded from memory. It is never cached or logged.")
        disclaimer.setObjectName("Disclaimer")
        disclaimer.setWordWrap(True)
        disclaimer.setFont(font_body())
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self.accept)
        
        layout.addWidget(title)
        layout.addWidget(disclaimer)
        layout.addWidget(self.password_input)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        submit_btn = QPushButton("Authenticate")
        submit_btn.setObjectName("Submit")
        submit_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(submit_btn)
        
        layout.addLayout(btn_layout)

    def get_password(self) -> str:
        pwd = self.password_input.text()
        self.password_input.clear()
        return pwd

class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle('Host Master')
        self.resize(1100, 700)
        self.setMinimumSize(900, 600)
        
        self._selected_node: ServerNode | None = None
        self._system_stats: SystemStats | None = None
        self._all_nodes: list[ServerNode] = []
        self._filter_query: str = ''
        self._current_view: int = 0  # 0=lattice, 1=table

        theme_manager.apply_palette_to_app()
        theme_manager.theme_changed.connect(self._on_theme_changed)
        
        self._build_ui()
        
        self._scanner = PortScannerWorker()
        self._scanner.scan_completed.connect(self._on_scan_completed)
        
        self._timer = QTimer(self)
        self._timer.setInterval(5000)
        self._timer.timeout.connect(self._trigger_scan)
        
        self._timer.start()
        self._trigger_scan()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._sidebar = Sidebar(self)
        self._sidebar.kill_requested.connect(self._kill_selected_process)
        self._sidebar.refresh_requested.connect(self._trigger_scan)
        self._sidebar.center_view_requested.connect(self._center_view)
        self._sidebar.toggle_view_requested.connect(self._toggle_view)
        self._sidebar.filter_changed.connect(self._on_filter_changed)
        layout.addWidget(self._sidebar)

        self._stack = QStackedWidget(self)

        self._lattice = LatticeGraphicsView(self)
        self._lattice.node_selected.connect(self._on_node_selected)
        self._lattice.hub_selected.connect(self._on_hub_selected)
        self._lattice.selection_cleared.connect(self._on_selection_cleared)
        self._stack.addWidget(self._lattice)

        self._table = AlternativeTableView(self)
        self._table.node_selected.connect(self._on_node_selected)
        self._table.selection_cleared.connect(self._on_selection_cleared)
        self._stack.addWidget(self._table)

        layout.addWidget(self._stack, stretch=1)

    def _on_theme_changed(self, mode: ThemeMode) -> None:
        t = theme_manager.tokens
        self.setStyleSheet(f'background-color: {ColorTokens.hex(t.bg_void)};')
        logger.debug('Theme changed to %s', mode.value)

    def _trigger_scan(self) -> None:
        if not self._scanner.isRunning():
            self._scanner.start()

    def _on_scan_completed(self, all_nodes: list[ServerNode], added_nodes: list[ServerNode], removed_keys: list[tuple[int,int]], stats: SystemStats) -> None:
        self._all_nodes = all_nodes
        self._system_stats = stats
        
        filtered = self._apply_filter(all_nodes)
        
        filtered_keys = {n.key for n in filtered}
        filtered_added = [n for n in added_nodes if n.key in filtered_keys]
        
        existing_keys = set(self._lattice.node_items.keys())
        filtered_removed = list((set(removed_keys) | (existing_keys - filtered_keys)))
        
        self._lattice.update_system_stats(stats)
        self._lattice.update_nodes_diff(filtered, filtered_added, filtered_removed)
        self._table.update_table(filtered)
        self._sidebar.update_system_stats(stats)
        
        if self._selected_node is not None and self._selected_node.key not in filtered_keys:
            self._on_selection_cleared()

    def _apply_filter(self, nodes: list[ServerNode]) -> list[ServerNode]:
        if not self._filter_query:
            return nodes
        q = self._filter_query.casefold()
        return [
            n for n in nodes
            if q in n.clean_name.casefold()
            or q in n.process_name.casefold()
            or q in str(n.port)
            or q in n.ip
        ]

    def _on_filter_changed(self, text: str) -> None:
        self._filter_query = text.strip()
        filtered = self._apply_filter(self._all_nodes)
        existing_keys = set(self._lattice.node_items.keys())
        filtered_keys = {n.key for n in filtered}
        filtered_removed = list(existing_keys - filtered_keys)
        filtered_added = [n for n in filtered if n.key not in existing_keys]
        self._lattice.update_nodes_diff(filtered, filtered_added, filtered_removed)
        self._table.update_table(filtered)

    def _reveal_hidden_node(self, node: ServerNode, pwd: str) -> bool:
        import subprocess, re
        try:
            proc_ss = subprocess.run(
                ['sudo', '-S', 'ss', '-lptn', f'sport = :{node.port}'],
                input=pwd.encode() + b'\n',
                capture_output=True,
                timeout=5
            )
            if proc_ss.returncode != 0:
                err = proc_ss.stderr.decode().strip()
                if "incorrect password" in err.lower():
                    self._show_error("Authentication Failed", "Incorrect sudo password.")
                else:
                    self._show_error("Error", f"Could not inspect port {node.port}.")
                return False
                
            out = proc_ss.stdout.decode().strip()
            match = re.search(r'users:\(\("([^"]+)",(?:pid=)?(\d+)', out)
            if not match:
                self._show_error("Error", f"Could not parse process info for port {node.port}.")
                return False
                
            name = match.group(1)
            real_pid = int(match.group(2))
            
            proc_cmd = subprocess.run(
                ['sudo', '-S', 'cat', f'/proc/{real_pid}/cmdline'],
                input=pwd.encode() + b'\n',
                capture_output=True,
                timeout=5
            )
            args = proc_cmd.stdout.decode().replace('\x00', ' ').strip()
            if not args:
                args = name
                
            self._scanner.revealed_ports[node.port] = (real_pid, name, args)
            return True
        except Exception as e:
            self._show_error('Error', str(e))
        return False

    def _on_node_selected(self, node: ServerNode) -> None:
        self._selected_node = node
        self._sidebar.update_selected_node(node)
        
        if node.pid == 0 and node.port not in self._scanner.revealed_ports:
            # Prevent mouse-lock by waiting until the user physically releases the mouse button
            self._prompt_reveal_node(node)

    def _prompt_reveal_node(self, node: ServerNode) -> None:
        if QApplication.mouseButtons() != Qt.MouseButton.NoButton:
            # Mouse is still held down. Try again in 50ms.
            QTimer.singleShot(50, lambda: self._prompt_reveal_node(node))
            return

        if self._selected_node != node:
            return  # They clicked away before releasing

        dialog = SudoDialog(f"Port {node.port} is protected. Authenticate to reveal details.", self)
        if dialog.exec() == QDialog.Accepted:
            pwd = dialog.get_password()
            if pwd:
                if self._reveal_hidden_node(node, pwd):
                    # Update the local node object immediately so the UI reflects it
                    real_pid, r_name, r_cmd = self._scanner.revealed_ports[node.port]
                    node.pid = real_pid
                    node.process_name = r_name
                    node.cmdline = r_cmd
                    node.clean_name = clean_process_name(r_name)
                    node.display_label = f"{node.clean_name} \u2022 {node.port}"
                    self._sidebar.update_selected_node(node)
                    self._trigger_scan()

    def _on_hub_selected(self, stats: SystemStats | None) -> None:
        self._selected_node = None
        self._sidebar.update_selected_hub(stats)

    def _on_selection_cleared(self) -> None:
        self._selected_node = None
        self._sidebar.clear_selection()

    def _center_view(self) -> None:
        self._lattice.reset_view()

    def _toggle_view(self) -> None:
        self._current_view = 1 - self._current_view
        self._stack.setCurrentIndex(self._current_view)
        # Update the button text to show the target view
        is_lattice = (self._current_view == 0)
        self._sidebar._actions.set_view_label(is_lattice)

    def closeEvent(self, event) -> None:
        logger.info('Shutting down Hostmaster')
        self._timer.stop()
        try:
            self._lattice.anim_timer.stop()
        except Exception:
            pass
        if self._scanner.isRunning():
            self._scanner.stop()
            self._scanner.quit()
            if not self._scanner.wait(2000):
                logger.warning('Scanner thread did not exit cleanly — forcing termination')
                self._scanner.terminate()
        super().closeEvent(event)

    def _kill_selected_process(self) -> None:
        if self._selected_node is None:
            return

        node = self._selected_node
        clean = node.clean_name or clean_process_name(node.process_name)

        if node.pid == 0:
            dialog = SudoDialog(f"Port {node.port} is owned by a protected process (e.g., Docker).", self)
            if dialog.exec() != QDialog.Accepted:
                return
            pwd = dialog.get_password()
            if not pwd:
                return
            
            try:
                proc = subprocess.run(
                    ['sudo', '-S', 'fuser', '-k', f'{node.port}/tcp'],
                    input=pwd.encode() + b'\n',
                    capture_output=True,
                    timeout=5
                )
                if proc.returncode != 0:
                    err = proc.stderr.decode().strip()
                    if "incorrect password" in err.lower():
                        self._show_error("Authentication Failed", "Incorrect sudo password.")
                    else:
                        self._show_error("Kill Failed", f"Could not terminate port {node.port}:\n{err}")
                    return
                logger.info(f"Port {node.port} terminated via sudo fuser.")
                self._on_selection_cleared()
                self._trigger_scan()
                return
            except Exception as e:
                self._show_error('Unexpected Error', f'An unexpected error occurred: {e}')
                return

        try:
            proc = psutil.Process(node.pid)
            if not proc.is_running():
                raise psutil.NoSuchProcess(node.pid)
        except psutil.NoSuchProcess:
            self._show_info(
                'Process Gone',
                f'{clean} (PID {node.pid}) is no longer running.',
            )
            self._trigger_scan()
            return
        except psutil.AccessDenied:
            dialog = SudoDialog(f"Cannot access PID {node.pid}.", self)
            if dialog.exec() != QDialog.Accepted:
                return
            pwd = dialog.get_password()
            if not pwd:
                return
            
            try:
                proc_cmd = subprocess.run(
                    ['sudo', '-S', 'kill', '-9', str(node.pid)],
                    input=pwd.encode() + b'\n',
                    capture_output=True,
                    timeout=5
                )
                if proc_cmd.returncode != 0:
                    err = proc_cmd.stderr.decode().strip()
                    if "incorrect password" in err.lower():
                        self._show_error("Authentication Failed", "Incorrect sudo password.")
                    else:
                        self._show_error("Kill Failed", f"Could not terminate PID {node.pid}:\n{err}")
                    return
                logger.info(f"PID {node.pid} terminated via sudo.")
                self._on_selection_cleared()
                self._trigger_scan()
                return
            except Exception as e:
                self._show_error('Unexpected Error', f'An unexpected error occurred: {e}')
                return

        dialog = TerminateDialog(clean, node.port, node.pid, self)
        if dialog.exec() != QDialog.Accepted:
            return

        try:
            proc.terminate()
            try:
                proc.wait(timeout=1.5)
                logger.info('Process %d (%s) terminated cleanly', node.pid, clean)
            except psutil.TimeoutExpired:
                logger.warning('Process %d did not exit on SIGTERM, sending SIGKILL', node.pid)
                proc.kill()
                proc.wait(timeout=1.0)
        except psutil.NoSuchProcess:
            logger.info('Process %d already gone by termination time', node.pid)
        except psutil.AccessDenied as e:
            self._show_error('Permission Denied', f'Could not terminate PID {node.pid}: {e}')
            return
        except OSError as e:
            self._show_error('OS Error', f'System error terminating PID {node.pid}: {e}')
            return
        except Exception as e:
            logger.exception('Unexpected error terminating PID %d', node.pid)
            self._show_error('Unexpected Error', f'An unexpected error occurred: {e}')
            return

        self._on_selection_cleared()
        self._trigger_scan()

    def _show_error(self, title: str, message: str) -> None:
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setIcon(QMessageBox.Critical)
        msg.exec()

    def _show_info(self, title: str, message: str) -> None:
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setIcon(QMessageBox.Information)
        msg.exec()

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    )
    app = QApplication(sys.argv)
    
    import os
    from PySide6.QtGui import QIcon
    icon_path = os.path.join(os.path.dirname(__file__), "assets", "hostmaster_app_icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
        
    app.setOrganizationName('HostMaster')
    app.setApplicationName('Host Master')
    app.setStyle('Fusion')
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
