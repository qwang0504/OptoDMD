import cv2
from PyQt5.QtCore import pyqtSignal, Qt, pyqtSlot
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QScrollArea, QPushButton, QFrame, QLineEdit, QCheckBox
import numpy as np
from numpy.typing import NDArray
from typing import Optional, List
from image_tools import im2uint8, im2rgb, DrawPolyMask
from qt_widgets import LabeledSpinBox

class DrawPolyMaskOpto(QWidget):
    """
    Derived class implementing slots to receive, delete, clear, flatten,
    or hide masks
    """

    mask_drawn = pyqtSignal(int, int, np.ndarray) #ID, Bool, mask_gray?

    def __init__(self, drawer: DrawPolyMask, *args, **kwargs):
    
        super().__init__(*args, **kwargs)

        self.drawer = drawer
        self.drawer.mask_drawn.connect(self.mask_drawn)
        self.create_components()
        self.layout_components()

    def get_ID(self):
        return self.drawer.get_ID()

    def set_ID(self, ID: int):
        self.drawer.set_ID(ID)

    def get_masks(self):
        return self.drawer.get_masks()
    
    def set_masks(self, masks: dict):
        return self.drawer.set_masks(masks)

    def get_image(self):
        return self.drawer.get_image()

    def set_image(self, image: np.ndarray):
        self.drawer.set_image(image)

    def update_pixmap(self):
        self.drawer.update_pixmap()

    def get_image_size(self):
        return self.drawer.get_image_size()

    def create_components(self):

        # special masks
        self.checkerboard = QPushButton(self)
        self.checkerboard.setText('checkerboard')
        self.checkerboard.clicked.connect(self.create_checkerboard)

        self.whole_field = QPushButton(self)
        self.whole_field.setText('whole field')
        self.whole_field.clicked.connect(self.create_whole_field)

    def layout_components(self):

        draw_buttons_layout = QHBoxLayout()
        draw_buttons_layout.addWidget(self.checkerboard)
        draw_buttons_layout.addWidget(self.whole_field)
        draw_buttons_layout.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(draw_buttons_layout)
        layout.addWidget(self.drawer)

    def on_mask_receive(self, recipient: int, key: int, mask: NDArray):
         
        if recipient == self.get_ID():

            # store mask
            show_mask = True
            masks = self.get_masks()
            masks[key] = (show_mask, mask)
            self.set_masks(masks)

        self.update_pixmap()

    def on_mask_delete(self, key: int):

        # remove mask from storage
        masks = self.get_masks()
        masks.pop(key)
        self.set_masks(masks)
        self.update_pixmap()

    def on_mask_clear(self):

        # remove mask from storage
        self.set_masks({})
        self.update_pixmap()

    def on_mask_flatten(self):
        
        # flatten masks
        flat = np.zeros(self.get_image_size(), dtype=np.float32)
        masks = self.get_masks()
        for key, mask_tuple in masks.items():
            mask = mask_tuple[1]
            flat += mask
        flat = np.clip(flat,0,1)

        # store flat mask
        masks = {}
        masks[1] = (True, flat)
        self.set_masks(masks)

        # update display
        self.update_pixmap()

    def on_mask_visibility(self, key: int, visibility: bool):

        masks = self.get_masks()
        _, mask = masks[key]
        masks[key] = (visibility, mask)
        self.set_masks(masks)
        self.update_pixmap()

    def create_checkerboard(self):
        
        # create key
        masks = self.get_masks()
        mask_keys = masks.keys() or [0]
        key = max(mask_keys) + 1

        # create checkerboard (8 cells in smallest dimension)
        h, w = self.get_image_size()
        num_pixels = min(w,h) // 8
        xv, yv = np.meshgrid(range(w), range(h), indexing='xy')
        checkerboard = ((xv // num_pixels) + (yv // num_pixels)) % 2
        checkerboard = checkerboard.astype(np.float32)

        # update masks
        masks[key] = (True, checkerboard)
        self.set_masks(masks)

        self.update_pixmap()

        # send signal
        self.mask_drawn.emit(self.get_ID(), key, checkerboard)
    
    def create_whole_field(self):

        # create key
        masks = self.get_masks()
        mask_keys = masks.keys() or [0]
        key = max(mask_keys) + 1
        
        # create whole field
        whole_field = np.ones(self.get_image_size(), dtype=np.float32)

        # update masks
        masks[key] = (True, whole_field)
        self.set_masks(masks)

        self.update_pixmap()

        # send signal
        self.mask_drawn.emit(self.get_ID(), key, whole_field)

class DrawPolyMaskOptoDMD(DrawPolyMaskOpto):
    '''
    Derived class that emits the collection of visible masks 
    '''

    DMD_update = pyqtSignal(np.ndarray)

    def update_pixmap(self):
        super().update_pixmap()
        #self.DMD_update.emit(im2uint8(self.im_display))

    def expose(self, key: int):
        masks = self.get_masks()
        visible, mask = masks[key]
        self.DMD_update.emit(mask)
        
    def clear(self):
        black = np.zeros(self.get_image_size(), np.uint8)
        self.DMD_update.emit(black)

class MaskItem(QWidget):

    showClicked = pyqtSignal(int,int)
    deletePressed = pyqtSignal(int)
    maskExpose = pyqtSignal(int)
    nameChange = pyqtSignal(int, str)

    def __init__(self, mask_index: int, name: Optional[str] = "name", *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.mask_index = mask_index
        self.name = name 
        self.create_components()
        self.layout_components()

    def create_components(self):
        
        self.show = QCheckBox(self)
        self.show.setCheckState(Qt.Checked)
        self.show.stateChanged.connect(self.show_clicked)

        self.name_label = QLineEdit(self)
        self.name_label.setText(self.name)
        self.name_label.editingFinished.connect(self.change_name)

        self.delete = QPushButton(self)
        self.delete.setText('X')
        self.delete.setMaximumWidth(25)
        self.delete.pressed.connect(self.delete_clicked)

        self.expose = QPushButton(self)
        self.expose.setText('Expose')
        self.expose.setMaximumWidth(75)
        self.expose.pressed.connect(self.expose_clicked)

    def layout_components(self):
        
        layout = QHBoxLayout(self)
        layout.addWidget(self.show)
        layout.addWidget(self.name_label)
        layout.addWidget(self.delete)
        layout.addWidget(self.expose)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
    
    def change_name(self):
        self.name = self.name_label.text()
        self.nameChange.emit(self.mask_index, self.name)

    def show_clicked(self):
        visible = (self.show.checkState() == Qt.Checked)
        self.showClicked.emit(self.mask_index, visible)

    def delete_clicked(self):
        self.deletePressed.emit(self.mask_index)

    def expose_clicked(self):
        self.maskExpose.emit(self.mask_index)

class MaskManager(QWidget):
    
    send_mask = pyqtSignal(int, int, np.ndarray)
    delete_mask = pyqtSignal(int) 
    flatten_mask = pyqtSignal()
    clear_mask = pyqtSignal()
    mask_visibility = pyqtSignal(int, int)
    mask_expose = pyqtSignal(int)
    clear_dmd = pyqtSignal()

    def __init__(
        self,
        mask_drawers: List[DrawPolyMaskOpto],
        mask_drawer_names: List[str],
        transformations: NDArray, 
        *args, **kwargs
    ):
        super().__init__(*args, **kwargs)

        N = len(mask_drawers)
        if not np.all(transformations.shape == np.array([N,N,3,3])):
            raise ValueError(f"transformations should be a {[N,N,3,3]} array")

        self.mask_widgets = {} 
        self.mask_drawers = mask_drawers
        self.mask_drawer_names = mask_drawer_names
        self.transformations = transformations 
        self.create_components()
        self.layout_components()

        for idx, drawer in enumerate(self.mask_drawers):
            drawer.set_ID(idx)
            drawer.mask_drawn.connect(self.on_mask_receive)

            self.send_mask.connect(drawer.on_mask_receive)
            self.delete_mask.connect(drawer.on_mask_delete)
            self.mask_visibility.connect(drawer.on_mask_visibility)
            self.flatten_mask.connect(drawer.on_mask_flatten)
            self.clear_mask.connect(drawer.on_mask_clear)

    def create_components(self):

        # flatten button 
        self.flatten = QPushButton(self)
        self.flatten.setText('flatten')
        self.flatten.clicked.connect(self.on_flatten_mask)

        # clear button 
        self.clear = QPushButton(self)
        self.clear.setText('clear')
        self.clear.clicked.connect(self.on_clear_masks)

        self.mask_frame = QFrame(self)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.mask_frame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        # clear dmd 
        self.clear_dmd_button = QPushButton(self)
        self.clear_dmd_button.setText('clear DMD')
        self.clear_dmd_button.clicked.connect(self.clear_dmd)


    def layout_components(self):

        mask_buttons_layout = QHBoxLayout()
        mask_buttons_layout.addWidget(self.clear)
        mask_buttons_layout.addWidget(self.flatten)

        self.frame_layout = QVBoxLayout(self.mask_frame)
        self.frame_layout.addStretch()
        self.frame_layout.setContentsMargins(0,0,0,0)
        self.frame_layout.setSpacing(0)

        mask_controls = QVBoxLayout()
        mask_controls.addLayout(mask_buttons_layout)
        mask_controls.addWidget(self.scroll_area)
        mask_controls.addWidget(self.clear_dmd_button)

        tabs = QTabWidget()
        for drawer, name in zip(self.mask_drawers, self.mask_drawer_names):
            tabs.addTab(drawer, name)

        layout = QHBoxLayout(self)
        layout.addWidget(tabs)
        layout.addLayout(mask_controls)

    def on_mask_receive(self, drawer_ID: int, key: int, mask: NDArray):

        # transform and send to other drawers
        for idx, drawer in enumerate(self.mask_drawers):

            # don't send to yourself
            if not idx == drawer_ID:

                T = self.transformations[drawer_ID, idx, :2, :]
                shape = drawer.get_image_size()
                dsize = shape[::-1] # opencv expects (col, rows)
                mask_transformed = cv2.warpAffine(mask, T, dsize)
                self.send_mask.emit(idx, key, mask_transformed)
                
        # add widget 
        widget = MaskItem(key, str(key))
        widget.showClicked.connect(self.on_mask_visibility)
        widget.deletePressed.connect(self.on_delete_mask)
        widget.maskExpose.connect(self.on_mask_expose)
        self.mask_widgets[key] = widget
        self.frame_layout.insertWidget(self.frame_layout.count()-1, widget)
        #test code that uses signals and slots to print the name change signal 
        #self.mask_widgets[key].nameChange.connect(self.print_names_signal)  
 
    #test method to print modified mask names 
    def print_names(self):
        keys = self.mask_widgets.keys()
        for key in keys:
            if str(key) != self.mask_widgets[key].name:
                print(f'name changed from {key} to {self.mask_widgets[key].name}')

    def print_names_signal(self, key: int, name: str):
        print(f'name changed from {key} to {self.mask_widgets[key].name}')

    def on_delete_mask(self, key: int):

        # delete widget
        widget = self.mask_widgets.pop(key)
        self.frame_layout.removeWidget(widget)
        widget.deleteLater()

        # propagate to connected widgets
        self.delete_mask.emit(key)

    def on_mask_expose(self, key: int):
        self.mask_expose.emit(key)

    def on_mask_visibility(self, key: int, visibility: bool):

        # propagate to connected widgets
        self.mask_visibility.emit(key, visibility)

    def on_clear_masks(self):

        self.clear_mask.emit()

        for key, widget in self.mask_widgets.items():
            # delete widget
            self.frame_layout.removeWidget(widget)
            widget.deleteLater()

        self.mask_widgets = {}

    def on_flatten_mask(self):

        if self.mask_widgets:

            self.flatten_mask.emit()

            # remove widgets
            for key, widget in self.mask_widgets.items():
                self.frame_layout.removeWidget(widget)
                widget.deleteLater()
            self.mask_widgets = {}

            # update widget
            widget = MaskItem(1, "flat")
            widget.showClicked.connect(self.on_mask_visibility)
            widget.deletePressed.connect(self.on_delete_mask)
            widget.maskExpose.connect(self.on_mask_expose)
            self.frame_layout.insertWidget(self.frame_layout.count()-1, widget)
            self.mask_widgets[1] = widget

