import sys
import re
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QTextEdit, QPushButton, QLabel, 
                           QLineEdit, QFrame, QStyleFactory, QFileDialog,
                           QMessageBox, QProgressBar, QSplitter)
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor, QTextCursor
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QDateTime
from urllib.parse import urlparse
from collections import defaultdict

class URLProcessThread(QThread):
    progress_updated = pyqtSignal(int, int, int)  # processed, total, stage
    result_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, urls, static_extensions):
        super().__init__()
        self.urls = urls
        self.static_extensions = static_extensions
        self.is_running = True
        
    def run(self):
        try:
            total_urls = len(self.urls)
            url_groups = defaultdict(list)
            processed = 0
            batch_size = 1000
            
            # Stage 1: Initial filtering and grouping
            for i in range(0, total_urls, batch_size):
                if not self.is_running:
                    return
                    
                batch = self.urls[i:i + batch_size]
                filtered_batch = []
                
                for url in batch:
                    try:
                        parsed = urlparse(url)
                        path = parsed.path.lower()
                        if not any(path.endswith(ext) for ext in self.static_extensions):
                            filtered_batch.append(url)
                    except Exception:
                        continue
                
                for url in filtered_batch:
                    try:
                        base_signature, params, param_score = self.get_url_signature(url)
                        url_groups[base_signature].append((url, tuple(params), param_score))
                    except Exception:
                        continue
                
                processed += len(batch)
                self.progress_updated.emit(processed, total_urls, 1)
            
            # Stage 2: Final selection
            final_urls = []
            group_count = len(url_groups)
            processed_groups = 0
            
            for group in url_groups.values():
                if not self.is_running:
                    return
                    
                selected_params = set()
                sorted_urls = sorted(group[:100], key=lambda x: (len(x[1]), x[2]), reverse=True)
                
                for url, params, _ in sorted_urls:
                    params_key = frozenset(params)
                    if params_key not in selected_params and len(selected_params) < 5:
                        selected_params.add(params_key)
                        final_urls.append(url)
                
                processed_groups += 1
                self.progress_updated.emit(processed_groups, group_count, 2)
            
            self.result_ready.emit(final_urls)
            
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def stop(self):
        self.is_running = False
    
    def get_url_signature(self, url):
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            path = parsed.path.lower()
            
            path_parts = []
            for part in path.split('/'):
                if part:
                    if part.isdigit() or len(part) >= 32:
                        part = '{param}'
                    path_parts.append(part)
            
            base_path = '/'.join(path_parts)
            base_signature = f"{netloc}{base_path}"
            
            params, param_score = self.analyze_query_params(parsed.query)
            
            return base_signature, params, param_score
            
        except Exception as e:
            return url, set(), 0
    
    def analyze_query_params(self, query_string):
        if not query_string:
            return set(), 0

        noise_params = {
            'timestamp', 'time', 't', 'random', 'rand',
            'v', 'version', '_', '_t', 'cache',
            'utm_source', 'utm_medium', 'utm_campaign',
            'ga', '_ga', 'fbclid', 'ref', 'source'
        }
        
        params = set()
        param_score = 0
        
        for param in query_string.split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                key = key.lower()
                
                if key in noise_params:
                    continue
                    
                params.add(key)
                
                if value:
                    if value.isdigit():
                        param_score += 1
                    elif any(c in value for c in '[]{}()|,;'):
                        param_score += 2
                    elif len(value) > 20:
                        param_score += 1.5
                    else:
                        param_score += 1
                        
        return params, param_score

class URLFilterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("URL过滤器")
        self.setMinimumSize(1200, 800)
        self.static_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.css', '.js'}
        self.filtered_urls = []  # Store filtered URLs for export
        
        # 设置应用主题
        self.setup_theme()
        
        # 创建主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 添加顶部标题栏
        self.add_title_bar(main_layout)
        
        # 添加内容区域
        self.add_content_area(main_layout)
        
        # 添加状态栏
        self.add_status_bar()
        
        # 初始化扩展名列表
        self.update_extensions_list()
        
        self.process_thread = None
    
    def setup_theme(self):
        """设置应用主题和样式"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f2f5;
            }
            QLabel {
                color: #2c3e50;
            }
            QFrame#titleBar {
                background-color: #1a73e8;
                border: none;
                padding: 10px;
            }
            QFrame#contentFrame {
                background-color: white;
                border: 1px solid #e1e4e8;
                border-radius: 10px;
                margin: 15px;
            }
            QTextEdit {
                border: 1px solid #e1e4e8;
                border-radius: 8px;
                padding: 10px;
                background-color: white;
                font-family: 'Microsoft YaHei';
                font-size: 11pt;
                selection-background-color: #cce8ff;
            }
            QTextEdit:focus {
                border: 2px solid #1a73e8;
            }
            QPushButton {
                background-color: #1a73e8;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-family: 'Microsoft YaHei';
                font-size: 11pt;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #1557b0;
            }
            QPushButton:pressed {
                background-color: #0d47a1;
            }
            QPushButton[warning="true"] {
                background-color: #dc3545;
            }
            QPushButton[warning="true"]:hover {
                background-color: #c82333;
            }
            QPushButton[secondary="true"] {
                background-color: #6c757d;
            }
            QPushButton[secondary="true"]:hover {
                background-color: #5a6268;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #e1e4e8;
                border-radius: 6px;
                background-color: white;
                font-family: 'Microsoft YaHei';
                font-size: 11pt;
            }
            QLineEdit:focus {
                border: 2px solid #1a73e8;
            }
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: #f0f2f5;
                height: 8px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #1a73e8;
                border-radius: 4px;
            }
            QSplitter::handle {
                background-color: #e1e4e8;
                margin: 1px;
            }
            QStatusBar {
                background-color: #f8f9fa;
                color: #6c757d;
            }
        """)

    def add_title_bar(self, layout):
        """添加顶部标题栏"""
        title_bar = QFrame()
        title_bar.setObjectName("titleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(20, 10, 20, 10)
        
        # 标题
        title = QLabel("URL 过滤工具")
        title.setFont(QFont('Microsoft YaHei', 16, QFont.Bold))
        title.setStyleSheet("color: white;")
        
        # 版本号
        version = QLabel("v2.0")
        version.setStyleSheet("color: rgba(255, 255, 255, 0.8);")
        version.setFont(QFont('Microsoft YaHei', 10))
        
        title_layout.addWidget(title)
        title_layout.addStretch()
        title_layout.addWidget(version)
        
        layout.addWidget(title_bar)

    def add_content_area(self, layout):
        """添加主要内容区域"""
        content_frame = QFrame()
        content_frame.setObjectName("contentFrame")
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        
        # 左侧面板
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # 右侧面板
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        # 设置分割比例
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        
        content_layout.addWidget(splitter)
        layout.addWidget(content_frame)

    def create_left_panel(self):
        """创建左侧面板"""
        panel = QFrame()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 10, 0)
        layout.setSpacing(15)
        
        # 输入区域
        input_group = QFrame()
        input_layout = QVBoxLayout(input_group)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(10)
        
        input_header = QLabel("输入URL")
        input_header.setFont(QFont('Microsoft YaHei', 12, QFont.Bold))
        
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("请输入URL，每行一个...")
        self.input_text.setMinimumHeight(200)
        
        input_layout.addWidget(input_header)
        input_layout.addWidget(self.input_text)
        
        # 按钮组
        button_group = QFrame()
        button_layout = QHBoxLayout(button_group)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        self.import_button = QPushButton("导入文本")
        self.import_button.setProperty('secondary', True)
        self.import_button.clicked.connect(self.import_text)
        
        self.filter_button = QPushButton("开始过滤")
        self.filter_button.clicked.connect(self.filter_urls)
        
        button_layout.addWidget(self.import_button)
        button_layout.addWidget(self.filter_button)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        
        # 结果区域
        result_header_layout = QHBoxLayout()
        
        result_header = QLabel("过滤结果")
        result_header.setFont(QFont('Microsoft YaHei', 12, QFont.Bold))
        
        self.export_button = QPushButton("导出结果")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_results)
        self.export_button.setProperty('secondary', True)
        
        result_header_layout.addWidget(result_header)
        result_header_layout.addStretch()
        result_header_layout.addWidget(self.export_button)
        
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setPlaceholderText("过滤结果将在这里显示...")
        self.results_text.setMinimumHeight(300)
        
        # 添加所有组件
        layout.addWidget(input_group)
        layout.addWidget(button_group)
        layout.addWidget(self.progress_bar)
        layout.addLayout(result_header_layout)
        layout.addWidget(self.results_text)
        
        return panel

    def create_right_panel(self):
        """创建右侧面板"""
        panel = QFrame()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(15)
        
        # 设置标题
        settings_header = QLabel("过滤设置")
        settings_header.setFont(QFont('Microsoft YaHei', 12, QFont.Bold))
        layout.addWidget(settings_header)
        
        # 单个扩展名添加
        ext_input_group = QFrame()
        ext_input_layout = QVBoxLayout(ext_input_group)
        ext_input_layout.setContentsMargins(0, 0, 0, 0)
        ext_input_layout.setSpacing(10)
        
        ext_label = QLabel("添加扩展名")
        ext_label.setFont(QFont('Microsoft YaHei', 11))
        
        input_row = QHBoxLayout()
        self.extension_input = QLineEdit()
        self.extension_input.setPlaceholderText("输入扩展名 (如: jpg)")
        
        add_ext_btn = QPushButton("添加")
        add_ext_btn.setFixedWidth(80)
        add_ext_btn.clicked.connect(self.add_extension)
        
        input_row.addWidget(self.extension_input)
        input_row.addWidget(add_ext_btn)
        
        ext_input_layout.addWidget(ext_label)
        ext_input_layout.addLayout(input_row)
        
        # 批量添加
        batch_label = QLabel("批量添加扩展名")
        batch_label.setFont(QFont('Microsoft YaHei', 11))
        
        self.batch_input = QTextEdit()
        self.batch_input.setPlaceholderText("用空格、逗号、分号或换行分隔\n例如: jpg, png, gif")
        self.batch_input.setMaximumHeight(80)
        
        batch_buttons = QHBoxLayout()
        add_batch_btn = QPushButton("批量添加")
        add_batch_btn.clicked.connect(self.add_batch_extensions)
        
        clear_all_btn = QPushButton("清空所有")
        clear_all_btn.setProperty('warning', True)
        clear_all_btn.clicked.connect(self.clear_all_extensions)
        
        batch_buttons.addWidget(add_batch_btn)
        batch_buttons.addWidget(clear_all_btn)
        
        # 当前扩展名列表
        current_label = QLabel("当前过滤扩展名")
        current_label.setFont(QFont('Microsoft YaHei', 11))
        
        self.extensions_text = QTextEdit()
        self.extensions_text.setReadOnly(True)
        self.extensions_text.setMinimumHeight(200)
        
        remove_btn = QPushButton("删除选中")
        remove_btn.setProperty('warning', True)
        remove_btn.clicked.connect(self.remove_selected_extensions)
        
        # 添加所有组件
        layout.addWidget(ext_input_group)
        layout.addWidget(batch_label)
        layout.addWidget(self.batch_input)
        layout.addLayout(batch_buttons)
        layout.addWidget(current_label)
        layout.addWidget(self.extensions_text)
        layout.addWidget(remove_btn)
        layout.addStretch()
        
        return panel

    def add_status_bar(self):
        """添加状态栏"""
        status_bar = self.statusBar()
        status_bar.showMessage("就绪")
        
    def update_progress(self, value, max_value=100):
        """更新进度条"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(max_value)
        self.progress_bar.setValue(value)
        QApplication.processEvents()
        
    def hide_progress(self):
        """隐藏进度条"""
        self.progress_bar.setVisible(False)
        QApplication.processEvents()
        
    def update_extensions_list(self):
        """更新扩展名列表显示"""
        extensions_list = sorted(self.static_extensions)
        self.extensions_text.clear()
        for ext in extensions_list:
            self.extensions_text.append(ext)

    def add_extension(self):
        """添加单个扩展名"""
        new_ext = self.extension_input.text().strip()
        if new_ext:
            if not new_ext.startswith('.'):
                new_ext = '.' + new_ext
            self.static_extensions.add(new_ext.lower())
            self.update_extensions_list()
            self.extension_input.clear()

    def add_batch_extensions(self):
        """批量添加扩展名"""
        batch_text = self.batch_input.toPlainText().strip()
        if batch_text:
            # 分割输入文本，支持空格、逗号、分号或换行符分隔
            extensions = re.split(r'[,;\s\n]+', batch_text)
            for ext in extensions:
                ext = ext.strip()
                if ext:
                    if not ext.startswith('.'):
                        ext = '.' + ext
                    self.static_extensions.add(ext.lower())
            self.update_extensions_list()
            self.batch_input.clear()

    def remove_selected_extensions(self):
        """删除选中的扩展名"""
        selected_text = self.extensions_text.textCursor().selectedText()
        if selected_text:
            extensions_to_remove = re.split(r'[\n\r]+', selected_text)
            for ext in extensions_to_remove:
                ext = ext.strip()
                if ext in self.static_extensions:
                    self.static_extensions.remove(ext)
            self.update_extensions_list()

    def clear_all_extensions(self):
        """清空所有扩展名"""
        self.static_extensions.clear()
        self.update_extensions_list()

    def analyze_query_params(self, query_string):
        """
        分析URL查询参数:
        1. 提取参数名和值
        2. 识别参数类型
        3. 过滤无意义的动态参数
        """
        if not query_string:
            return set(), 0

        # 需要过滤的动态参数
        noise_params = {
            'timestamp', 'time', 't', 'random', 'rand',
            'v', 'version', '_', '_t', 'cache',
            'utm_source', 'utm_medium', 'utm_campaign',
            'ga', '_ga', 'fbclid', 'ref', 'source'
        }
        
        params = set()
        param_score = 0
        
        for param in query_string.split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                key = key.lower()
                
                # 跳过动态参数
                if key in noise_params:
                    continue
                    
                params.add(key)
                
                # 计算参数分数
                if value:
                    if value.isdigit():  # 数字参数
                        param_score += 1
                    elif any(c in value for c in '[]{}()|,;'):  # 复杂参数
                        param_score += 2
                    elif len(value) > 20:  # 长字符串
                        param_score += 1.5
                    else:  # 普通参数
                        param_score += 1
                        
        return params, param_score

    def get_url_signature(self, url):
        """
        生成URL签名:
        1. 提取基本路径
        2. 识别动态路径部分
        3. 分析查询参数
        """
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            path = parsed.path.lower()
            
            # 处理路径中的动态部分
            path_parts = []
            for part in path.split('/'):
                if part:
                    # 如果是数字或长字符串,可能是动态ID
                    if part.isdigit() or len(part) >= 32:
                        part = '{param}'
                    path_parts.append(part)
            
            # 生成基本签名
            base_path = '/'.join(path_parts)
            base_signature = f"{netloc}{base_path}"
            
            # 分析查询参数
            params, param_score = self.analyze_query_params(parsed.query)
            
            return base_signature, params, param_score
            
        except Exception as e:
            print(f"URL签名生成失败: {url}, 错误: {str(e)}")
            return url, set(), 0

    def filter_urls(self):
        """
        URL过滤和分组逻辑:
        1. 过滤静态资源
        2. 按端点分组
        3. 保留不同参数组合
        """
        if self.process_thread and self.process_thread.isRunning():
            self.process_thread.stop()
            self.process_thread.wait()
            self.filter_button.setText("开始过滤")
            self.statusBar().showMessage("处理已取消")
            return
            
        input_urls = self.input_text.toPlainText().strip().split('\n')
        input_urls = [url.strip() for url in input_urls if url.strip()]
        total_urls = len(input_urls)
        
        if total_urls == 0:
            self.results_text.setText("请输入要处理的URL")
            return
        
        self.filter_button.setText("取消处理")
        self.results_text.setText("正在处理URL，请稍候...\n")
        self.progress_bar.setVisible(True)
        QApplication.processEvents()
        
        self.process_thread = URLProcessThread(input_urls, self.static_extensions)
        self.process_thread.progress_updated.connect(self.update_process_progress)
        self.process_thread.result_ready.connect(self.handle_results)
        self.process_thread.error_occurred.connect(self.handle_error)
        self.process_thread.finished.connect(self.process_finished)
        self.process_thread.start()
    
    def update_process_progress(self, processed, total, stage):
        progress = (processed / total) * 100
        self.update_progress(int(progress))
        stage_text = "过滤分组" if stage == 1 else "整理结果"
        self.results_text.setText(f"正在{stage_text}...\n已完成: {processed}/{total} ({progress:.1f}%)")
    
    def handle_results(self, final_urls):
        self.filtered_urls = final_urls  # Store filtered URLs
        if final_urls:
            result_text = f"处理完成！\n共处理 {len(self.process_thread.urls)} 个URL，过滤后保留 {len(final_urls)} 个URL。\n\n过滤结果：\n\n"
            result_text += "\n".join(final_urls)
            self.results_text.setText(result_text)
            self.export_button.setEnabled(True)  # Enable export button
        else:
            self.results_text.setText("没有找到符合条件的URL")
            self.export_button.setEnabled(False)  # Disable export button
            
    def handle_error(self, error_msg):
        self.results_text.setText(f"处理过程中发生错误：{error_msg}")
    
    def process_finished(self):
        self.filter_button.setEnabled(True)
        self.filter_button.setText("开始过滤")
        self.hide_progress()
        QApplication.processEvents()
    
    def import_text(self):
        """导入文本文件功能"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "选择文本文件",
                "",
                "文本文件 (*.txt);;所有文件 (*.*)"
            )
            
            if file_path:
                try:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        content = file.read()
                except UnicodeDecodeError:
                    # 如果UTF-8解码失败，尝试其他编码
                    encodings = ['gbk', 'gb2312', 'iso-8859-1']
                    content = None
                    for encoding in encodings:
                        try:
                            with open(file_path, 'r', encoding=encoding) as file:
                                content = file.read()
                                break
                        except UnicodeDecodeError:
                            continue
                    
                    if content is None:
                        raise UnicodeDecodeError("无法识别文件编码")
                
                # 统计URL数量
                urls = [url.strip() for url in content.split('\n') if url.strip()]
                url_count = len(urls)
                
                if url_count > 0:
                    # 更新文本框内容
                    self.input_text.setText(content)
                    QMessageBox.information(
                        self,
                        "导入成功",
                        f"成功导入 {url_count} 个URL"
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "导入警告",
                        "文件中没有找到有效的URL"
                    )
                    
        except Exception as e:
            QMessageBox.critical(
                self,
                "导入错误",
                f"导入文件时发生错误：{str(e)}"
            )

    def export_results(self):
        """导出过滤结果到文件"""
        if not self.filtered_urls:
            QMessageBox.warning(self, "导出警告", "没有可导出的URL")
            return
            
        try:
            # 获取当前时间作为默认文件名
            default_filename = f"filtered_urls_{QDateTime.currentDateTime().toString('yyyyMMdd_HHmmss')}.txt"
            
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "导出结果",
                default_filename,
                "文本文件 (*.txt);;所有文件 (*.*)"
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as file:
                    file.write("\n".join(self.filtered_urls))
                    
                QMessageBox.information(
                    self,
                    "导出成功",
                    f"成功导出 {len(self.filtered_urls)} 个URL到文件：\n{file_path}"
                )
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "导出错误",
                f"导出文件时发生错误：{str(e)}"
            )
    
def main():
    app = QApplication(sys.argv)
    window = URLFilterApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
