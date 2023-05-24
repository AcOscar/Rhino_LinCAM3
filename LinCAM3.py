#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015,2016,2017,2018 Daniel Fernandez MD (daniel@dfmd.mx), Saul Pilatowsky C (saul@dfmd.mx) 
# distributed by www.ingenierialinarand.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.



import Rhino
import scriptcontext as sc
import rhinoscriptsyntax as rs
import System
import Rhino.UI
import Eto.Drawing as drawing
import Eto.Forms as forms
import os
import json
import webbrowser
import operator
import sys
import shutil
from collections import OrderedDict
import traceback

COMMAND_NAME = "LinCAM3"
PLUGIN_NAME = "LinCAM"
VERSION = "CG-2023-1"
WEBPAGE = 'https://github.com/AcOscar/Rhino_LinCAM3'

# SampleEtoRoomNumber dialog class
class camDialog(forms.Form):

    # Dialog box Class initializer
    def __init__(self):
       
        # Rhino objects
        self.objects = None
        self.rhino_objects = None
        self.sorted_objects = None 
        self.model_objects = None
        # Total machining time
        self.cut_time = 0
        # Total object
        self.objects_count = None
        # Is code thread running
        self.code_thread = False
        # Console lines
        self.console_lines = ['','','']
        #Preview layer names
        self.layer_preview = 'CAM_Preview'
        self.layer_cluster = 'ClusterOrder_dots'
        self.layer_sorting = 'CutOrder_dots'
        self.preview_layer_name = "CAM preview"
        self.offset_layer = "Offset curves"
        self.layer_sorting = "Tags orden"
        self.layer_cluster = "Tags cluster"
        self.trash_layer = "Trash"
        #Language
        self.language = False
        self.language_text = False

    # Basic form initialization
    def Initialize(self,plugin_name,command_name,version,webpage):
        
        self.plugin_name = plugin_name
        self.command_name = command_name
        self.version = version
        self.webpage = webpage
        self.registry_section = "%s_reg" % self.command_name
        
        self.SetWorkingPaths()
        if not self.check_language_and_conditions(): return
    
         # Set working variables 
        self.machining_settings = self.get_machining_settings()
        self.user_data = self.get_user_data()
        self.general_settings = self.get_general_settings()
        self.postprocessors = self.get_postprocessors()
        self.machining_input = self.get_machining_input()
        #Since the rhino log is copied from file to file, it checks that the selected routine exists in that file.
        if self.user_data['selected_preset'] not in self.machining_settings: self.user_data['selected_preset'] = False
        #Check if there is any selected post if not assign the first one in the list.
        if not self.user_data['post']: self.user_data['post'] = sorted(self.postprocessors.keys())[-1]
        
        # Form settings
        self.Title = self.command_name
        self.Padding = drawing.Padding(5)
        self.Resizable = True
        self.Maximizable = False
        self.Minimizable = False
        self.ShowInTaskbar = False
        # FormClosed event handler
        self.Closed += self.OnFormClosed
        # Creates form control
        self.CreateMainForm()
        #Checks for preselected objects 
        valid_objects = self.SetObjectsByColor(self.get_selected_objects())
        if valid_objects: rs.SelectObjects(valid_objects)
        return True
    
    def SetWorkingPaths(self):
        try:
            try:
                work_folder = os.path.dirname(os.path.realpath(__file__))
                self.image_folder = os.path.join(work_folder, "res","Icons")
                settings_folder = os.path.join(work_folder, "res","Settings")
            except:
                id = Rhino.PlugIns.PlugIn.IdFromName(self.plugin_name)
                plugin_folder = os.path.dirname(Rhino.PlugIns.PlugIn.Find(id).Assembly.Location)
                plugin_version = os.path.basename(plugin_folder)
                local_folder = os.path.join(os.getenv('APPDATA'),self.command_name)# if rs.IsRunningOnWindows() else 
                local_settings = os.path.join(local_folder,plugin_version)
                plugin_settings = os.path.join(plugin_folder, "res","Settings")
                if not os.path.isdir(local_folder):
                    os.makedirs(local_folder)
                if not os.path.isdir(local_settings):
                    os.makedirs(local_settings)
                    for file_name in os.listdir(plugin_settings):
                        shutil.copy(os.path.join(plugin_settings,file_name),os.path.join(local_settings,file_name))
                settings_folder = local_settings
                self.image_folder = os.path.join(plugin_folder, "res","Icons")    
            
            self.machining_file = os.path.join(settings_folder,"MachiningSettings.json")
            self.machining_input_file = os.path.join(settings_folder,"MachiningInput.json")
            self.initial_settings_file = os.path.join(settings_folder,"InitialSettings.json")
            self.postprocessors_file = os.path.join(settings_folder,"Postprocessors.json")
            self.language_file = os.path.join(settings_folder,"LangFile.json")
         
        except Exception as e: print(e)
    
    def txt(self,txt):
        
        #Translates text if necessary
        if txt not in self.language_text:
            self.language_text[txt] = {'English':''}
        if self.language != 'Espanol' and self.language not in self.language_text[txt]:
            self.language_text[txt][self.language] = ''
        if self.language == 'Espanol' or not self.language_text[txt][self.language]:
            return txt
        else:
            return self.language_text[txt][self.language]
    
    def check_language_and_conditions(self):
        
        if os.path.isfile(self.language_file):
            with open(self.language_file,'r') as f:
                self.language_text = json.loads(f.read())
        else: self.language_text = {}
        
        if os.path.isfile(self.initial_settings_file):
            with open(self.initial_settings_file,"r") as f:
                input_language = json.loads(f.read())['language']
            self.language = input_language
        else:
            input_language =  rs.ListBox(["Espanol","English"], message='', title='Idioma/Language', default=None)
            if not input_language: return
            self.language = input_language
            
            terms = self.txt('El uso de este programa es responsabilidad del usuario final. Es una version en desarollo y no nos hacemos responsables por ningun problema que pueda causar. Esperamos te sea de utilidad. \n\nAceptas los terminos y condiciones?')
            if rs.MessageBox(terms, 4 | 32) == 6:
                with open(self.initial_settings_file,'w') as f:
                    f.write(json.dumps({'language':input_language}))
            else: return
        return True
    
    def get_machining_settings(self):
        local_data = self.read_json_file(self.machining_file)
        rhino_data = self.read_registry('machining_settings')
        if rhino_data and local_data:
            local_data.update(rhino_data)
        return local_data if local_data else rhino_data if rhino_data else {}

    def get_selected_objects(self):
        objects = self.read_registry('objects')
        if objects: return objects['objects']
        
    
    def get_general_settings(self):
        data = self.read_registry('general_settings')
        if not data:
            data = {"sec_plane":12,
                    "feed_rapid":20000,
                    "cut_diam":9.525,
                    "spindle":20000,
                    'tolerance':1}
        return data
    
    def get_machining_input(self):
        return self.read_json_file(self.machining_input_file)
    
    def get_postprocessors(self):
        return self.read_json_file(self.postprocessors_file)
       
    def get_user_data(self):
        data = self.read_registry('user_data')
        if not data: 
            data = {"post":False,
                   "save_file":False,
                   "material_info":False,
                   "sort_closest":False,
                   "sorting":True,
                   "autocluster":True,
                   "file_path":rs.DocumentPath(),
                   'file_name':rs.DocumentName().replace('.3dm','_gcode.nc') if rs.DocumentName() else False,
                   "selected_preset":self.machining_settings.keys()[0] if self.machining_settings else False,
                   "save_image":False,
                   }
        return data
    
    def read_registry(self,registry):
        data = rs.GetDocumentData(self.registry_section,registry)
        if data: return json.loads(data)
    
    def write_json_registry(self,registry,data):
        rs.SetDocumentData(self.registry_section,registry,json.dumps(data))
        return True
    
    def read_json_file(self,file_path):
        if os.path.isfile(file_path):
            with open(file_path,'r') as f:
                return json.loads(f.read())
    
    def write_json_file(self,file_path,content):
        with open(file_path,'w') as f:
            f.write(json.dumps(content,indent=4))
        return True
    
    def AddWorkingLayers():
        #Add layers to the file to make g_curve unwind
        if not rs.IsLayer(self.offset_layer):rs.AddLayer(self.offset_layer)
        else: rs.DeleteObjects(rs.ObjectsByLayer(self.offset_layer))
        if not rs.IsLayer(self.trash_layer):rs.AddLayer(self.trash_layer)
        else: rs.DeleteObjects(rs.ObjectsByLayer(self.trash_layer))
        return rs.CurrentLayer()
    
    def RemoveWorkingLayers(original_layer=False):
        rs.DeleteObjects(rs.ObjectsByLayer(self.offset_layer))
        rs.DeleteObjects(rs.ObjectsByLayer(self.trash_layer))
        rs.DeleteLayer(self.offset_layer)
        rs.DeleteLayer(self.trash_layer)
        if original_layer: rs.CurrentLayer(original_layer)
    
    def CleanLayer(self,layer,parent_layer=False):
        if parent_layer: rs.LayerLocked(parent_layer,False)
        if not rs.IsLayer(layer):rs.AddLayer(layer,parent=parent_layer)
        else:
            rs.LayerLocked(layer,False)
            rs.DeleteObjects(rs.ObjectsByLayer(layer))
        if parent_layer: rs.LayerLocked(parent_layer,True)
        rs.LayerLocked(layer,True)
        
    def AddPreviewLayers(self):
        self.CleanLayer(self.layer_preview)
        self.CleanLayer(self.layer_cluster,self.layer_preview)
        self.CleanLayer(self.layer_sorting,self.layer_preview)
    
    def GetObjectsID(self,reg_json=False):
        if not self.rhino_objects: return False
        objects_id = []
        for type,objects in self.rhino_objects.items():
            if objects:
                for object in objects: objects_id.append(str(object))
        return {'objects':objects_id} if reg_json else objects_id
    #Saves data
    def SaveData(self):
        try:
            temporal = {}
            persistant = {}
            for name,values in self.machining_settings.items():
                if values["persistant"]:temporal[name] = values
                else:persistant[name] = values
            self.write_json_registry("machining_settings", temporal)
            self.write_json_registry("general_settings",self.general_settings)
            self.write_json_registry("user_data",self.user_data)
            self.write_json_registry("objects",self.GetObjectsID(True))
            self.write_json_file(self.machining_file, persistant)
            self.write_json_file(self.postprocessors_file, self.postprocessors)
            self.write_json_file(self.language_file,self.language_text)
        except Exception as e: print('Save data error:',e)
    # Form Closed event handler
    def OnFormClosed(self, sender, e):
        # Remove the events added in the initializer
        #self.RemoveEvents()
        # Dispose of the form and remove it from the sticky dictionary
        self.SaveData()
        if sc.sticky.has_key(self.command_name):
            form = sc.sticky[self.command_name]
            if form:
                form.Dispose()
                form = None
            sc.sticky.Remove(self.command_name)
    
    # Return form image as icon    
    def Icon(self,name):
        image_view = forms.ImageView()
        image_view.Size = drawing.Size(20,20)
        image_view.Image = drawing.Bitmap(os.path.join(self.image_folder,name))
        return image_view
    
    def OnLinkButtonClick(self, sender, e):
        
        webbrowser.open(sender.Text)
        
    def ConsoleLog(self,logText):
        self.console_lines.append(logText)
        self.console_lines.pop(0)
        self.label1.Text = self.console_lines[0]
        self.label2.Text = self.console_lines[1]
        self.label3.Text = self.console_lines[2]
        
    def LayoutToGroupbox(self,name,layout):
        groupbox = forms.GroupBox(Text = name)
        groupbox.Padding = drawing.Padding(3)
        groupbox.Content = layout
        return groupbox
    
    def CreateMainForm(self):
         # Create table layout
        layout = forms.DynamicLayout()
        layout.Padding = drawing.Padding(10)
        layout.Spacing = drawing.Size(5, 5)
        # Create secondary layouts
        Header = self.CreateHeader()
        SelectControls = self.CreateSelectControls()
        #PresetControls = self.CreatePresetControls()
        #GeneralSettings = self.CreateGeneralSettings()
        Console = self.LayoutToGroupbox('Console',self.CreateConsole())
        Checkboxes = self.CreateCheckboxControls()
        PostControls = self.CreatePostrocessorControls()
        
        #Create big save button
        SaveButton = forms.Button(Text = self.txt('Generar codigo'))
        
        machining_settings = [name for name in sorted(["* %s"%i if self.machining_settings[i]["persistant"] else "%s"%i for i in self.machining_settings])]
        preset_name = self.user_data["selected_preset"] if self.user_data["selected_preset"] else ''
        preset_description = self.machining_settings[preset_name]['descripcion'] if preset_name else ''
        
        self.SelectedPresetText = forms.Label(Text = preset_description)
        
        SaveButton.Click += self.make_code
        #Progress bar for slow computers
        self.progressbar = forms.ProgressBar()
        self.progressbar.MinValue = 0
        self.progressbar.MaxValue = 5

        # Add controls to layout
        layout.AddRow(Header)
        layout.AddRow(None)
        layout.AddRow(PostControls)
        layout.AddRow(None)
        layout.AddRow(None)
        layout.AddRow(SelectControls)
        layout.AddRow(None)
        layout.AddRow(self.SelectedPresetText)
        layout.AddRow(None)
        layout.AddRow(None)
        layout.AddRow(Checkboxes)
        layout.AddRow(None)
        
        #layout.AddRow(PresetControls)
        #layout.AddRow(None)
        layout.AddRow(None)
        #layout.AddRow(GeneralSettings)
        
        
        layout.AddRow(None)
        layout.AddRow(None)
        layout.AddRow(SaveButton)
        layout.AddRow(self.progressbar)
        layout.AddRow(None)
        layout.AddRow(Console)
        
        
        self.Content = layout
    
    def CreateConsole(self):
        
        layout = forms.DynamicLayout()
        layout.Spacing = drawing.Size(3, 3)
        
        self.label1 = forms.Label(Text = '')
        self.label2 = forms.Label(Text = '')
        self.label3 = forms.Label(Text = '')
        
        layout.AddRow(self.label1)
        layout.AddRow(self.label2)
        layout.AddRow(self.label3)

        return layout
    
    def CreateHeader(self):
        
         # Create table layout
        layout = forms.DynamicLayout()
        layout.Spacing = drawing.Size(3, 3)
        # image header and info
        HeaderText = forms.Label(Text = self.version)
        HeaderLink = forms.LinkButton(Text = self.webpage)
        HeaderLink.Click += self.OnLinkButtonClick
        HeaderLogo = forms.ImageView()
        #HeaderLogo.Size = drawing.Size(50,100)
        HeaderLogo.Image = drawing.Bitmap(os.path.join(self.image_folder,'Logo','Rhino_LinCAM3_100.png'))
         # Add controls to layout
        layout.AddRow(HeaderLogo,None,HeaderText,HeaderLink)
        return layout
    
    def NumericUpDown(self,DecimalPlaces=False,Increment=False,MaxValue=False,MinValue=False,Value=False):
        numeric_updown = forms.NumericUpDown()
        numeric_updown.DecimalPlaces = DecimalPlaces
        numeric_updown.Increment = Increment
        numeric_updown.MaxValue = MaxValue
        numeric_updown.MinValue = MinValue
        numeric_updown.Value = Value
        numeric_updown.ValueChanged += self.set_general_settings
        return numeric_updown
    
    def CreateGeneralSettings(self):
     
         # Create table layout
        layout = forms.DynamicLayout()
        layout.Spacing = drawing.Size(10, 3)
        # Numeric General inputs
        self.general_inputs = {}
        ordered_names = ["cut_diam","sec_plane","tolerance","feed_rapid","spindle"]
        for name in ordered_names:
            values = self.machining_input['GENERAL_INPUT'][name]
            input_row = {}
            for setting, data in values.items():
                if setting == 'input':
                    data['Value'] = self.general_settings[name]
                    input_row[setting] = self.NumericUpDown(**data)
                elif setting == 'image':
                    input_row[setting] = self.Icon(data)
                elif setting in ['name','unit']:
                    input_row[setting] = forms.Label(Text = self.txt(data))
            self.general_inputs[name] = input_row
            layout.AddRow(input_row['image'],input_row['name'],input_row['input'],input_row['unit'])
        
        return layout
    
     # Create all of the checkbox controls used by the form
    def CreateCheckboxControls(self):
        
        layout = forms.DynamicLayout()
        layout.Spacing = drawing.Size(10, 3)
        ordered_checkboxes = ['sorting','sort_closest','autocluster','save_image']
        self.checkbox_inputs = {}
        for name in ordered_checkboxes:
            values = self.machining_input['CHECKBOX_INPUT'][name]
            checkbox = forms.CheckBox(Text = self.txt(values['name']))
            checkbox.CheckedChanged += self.set_user_data
            checkbox.Checked = self.user_data[name]
            image = self.Icon(values['image'])
            self.checkbox_inputs[name] = checkbox
            layout.AddRow(image,checkbox)
        return layout                 
            
    def CreateSelectControls(self):
        
        machining_settings = sorted(self.machining_settings.keys())
        preset_name = self.user_data["selected_preset"] if self.user_data["selected_preset"] else ''
        preset_description = self.machining_settings[preset_name]['descripcion'] if preset_name else ''
        # Create table layout
        layout = forms.DynamicLayout()
        layout.Spacing = drawing.Size(3, 3)
        
        SelectIcon = self.Icon('curves.png')
        
        self.dropdownlist_settings = forms.DropDown()
        self.dropdownlist_settings.DataStore = machining_settings
        self.dropdownlist_settings.SelectedIndex = machining_settings.index(self.user_data["selected_preset"]) if self.user_data["selected_preset"] else 0
        self.dropdownlist_settings.DropDownClosed += self.set_machining_settings
        
        NewButton_settings = forms.Button(Text = self.txt('Nuevo'))
        NewButton_settings.Click += self.new_settings
       
        EditButton_settings = forms.Button(Text = self.txt('Editar'))
        EditButton_settings.Click += self.edit_settings
        
        DeleteButton_settings = forms.Button(Text = self.txt('Borrar'))
        DeleteButton_settings.Click += self.delete_settings
        
        #Help link
#         HelpLink = forms.LinkButton(Text = self.txt('Ayuda JSON'))
#         HelpLink.Click += self.show_json_help
        # Add controls to layout
        #layout.AddRow(PostLabel,None)
        
        layout.AddRow(SelectIcon,self.dropdownlist_settings,None,NewButton_settings,EditButton_settings,DeleteButton_settings)
        return layout
    
    def CreatePostrocessorControls(self):
        

        # Create table layout
        layout = forms.DynamicLayout()
        layout.Spacing = drawing.Size(3, 3)
        
        PostIcon = self.Icon('gcode.png')
        self.dropdownlist = forms.DropDown()
        self.dropdownlist.DataStore = [name for name in sorted(self.postprocessors.keys())]
        self.dropdownlist.SelectedIndex = sorted(self.postprocessors.keys()).index(self.user_data['post'])
        self.dropdownlist.DropDownClosed += self.set_postprocessor
        
        
        NewButton = forms.Button(Text = self.txt('Nuevo'))
        NewButton.Click += self.new_postprocessors
       
        EditButton = forms.Button(Text = self.txt('Editar'))
        EditButton.Click += self.edit_postprocessors
        
        DeleteButton = forms.Button(Text = self.txt('Borrar'))
        DeleteButton.Click += self.delete_postprocessors
        #Help link
#         HelpLink = forms.LinkButton(Text = self.txt('Ayuda JSON'))
#         HelpLink.Click += self.show_json_help
        
        # Add controls to layout
        #layout.AddRow(PostLabel,None)
        layout.AddRow(PostIcon,self.dropdownlist,None,NewButton,EditButton,DeleteButton)
       
        return layout
    
    def CreatePresetControls(self):
        
        # Create table layout
        layout = forms.DynamicLayout()
        layout.Spacing = drawing.Size(3, 3)
    
        # New Button
        NewIcon = self.Icon('new.png')
        NewButton = forms.Button(Text = self.txt('Nueva rutina'))
        NewButton.Click += self.new_settings
        # Edit Button
        EditIcon = self.Icon('edit.png')
        EditButton = forms.Button(Text = self.txt('Editar'))
        EditButton.Click += self.edit_settings
        
         # Delete Button
        DeleteIcon = self.Icon('edit.png')
        DeleteButton = forms.Button(Text = self.txt('Borrar'))
        DeleteButton.Click += self.delete_settings
        
        # Add controls to layout
        layout.AddRow(NewButton,
                      EditButton,
                      None,
                      DeleteButton,
                      )
        
        return layout
    
    def ValidateData(self,in_value,var_name):
        
        try:in_value = float(in_value)
        except:
            self.ConsoleLog('%s: %s: %s=0.0' % (self.txt('ADVERTENCIA'),self.txt('Valor no numerico se reemplazo'),var_name))
            return 0.0
        if var_name in ["feed","feed_cut","feed_plunge","entries"]:    
            if in_value < 1:in_value = 1.0
        if var_name in ["plunge"]:    
            if in_value <= 0:in_value = 0.01
        if var_name in ["xy_dist"]:
            if in_value < .1 or in_value > 1:in_value = .5
        if var_name in ["depth"]:
            if in_value > -.01:in_value = in_value * -1
        return in_value            
    
    def ValidateName(self,name,input_dict):
        name = name if name else self.txt('SinNombre')
        suffix = 1
        while name in input_dict:
            name = '%s_%s' % (name,suffix)
        return name
    
    def ValidateObjects(self,objects):
        validated = []
        for obj in objects:
            if rs.IsObject(obj):validated.append(obj)
        return validated
     
    
    def CreateSettings(self,edit = False):
        # The script that will be using the dialog.
  
        dialog_data = {}
        preset_name = self.user_data["selected_preset"] if self.user_data["selected_preset"] else ''
        preset_description = self.machining_settings[preset_name]['descripcion'] if preset_name else ''
        persistant = self.machining_settings[preset_name]['persistant'] if preset_name else 0
        
        for comp, values in self.machining_input['MACHINING_INPUT'].items():
            var_names = [i[0] for i in values]
            input_names = [self.txt(i[1]) for i in values]
            input_values = [0 for i in var_names] if not preset_name else [self.machining_settings[preset_name][comp][i] for i in var_names]
            dialog_data[comp] = [[input_names[i],input_values[i]] for i in range(len(values))]
        
        title = self.txt('Editar rutina de corte') if edit else self.txt('Nueva rutina de corte')
        dialog = editDialog(title,preset_name if edit else '',preset_description,dialog_data,'preset',persistant=persistant,language=self.language,language_text=self.language_text)
        rc = dialog.ShowModal(Rhino.UI.RhinoEtoApp.MainWindow)
        if rc:
            new_settings = {}
            for comp, values in self.machining_input['MACHINING_INPUT'].items():
                var_names = [i[0] for i in values]
                dialog_values = dialog.GetSettings(comp)
                new_settings[comp] = {var_names[i]:self.ValidateData(dialog_values[i],var_names[i]) for i in range(len(var_names))}
            new_settings['persistant'] = dialog.SaveLocally()
            new_settings['descripcion'] = dialog.GetDescription()
            
            if edit: del self.machining_settings[self.user_data["selected_preset"]] 
            
            new_name = self.ValidateName(dialog.GetName(),self.machining_settings)
            self.user_data['selected_preset'] = new_name
            self.machining_settings.update({new_name:new_settings})
            #self.SelectSettingsText.Text = new_name
            #self.SelectSettingsDescription.Text = new_settings['descripcion']
            self.ConsoleLog('%s: %s' % (self.txt('Rutina actualizada'),new_name))
            
    def CreatePostprocessor(self,edit = False):
        # The script that will be using the dialog.
        try:
            post_name = self.user_data["post"] if edit else ''
            post_data = self.postprocessors[post_name] if edit else False
            post_description = self.postprocessors[post_name]['description'] if edit else ''
            dialog_input = []
            for input_data in self.machining_input['POST_INPUT']:
                data = post_data[input_data['var']] if edit else input_data['value']
                if input_data['type'] == 'list' and edit:
                    data = ','.join(data)
                dialog_input.append([self.txt(input_data['name']),data])
            dialog_data = {'Code':dialog_input}
            title = self.txt('Editar postprocesador') if edit else self.txt('Nuevo postprocesador')
            messages = ['Notas:','Utiliza comas para agregar varias lineas.','Deja en blanco para omitir.','Revisa bien tu codigo.']
            dialog = editDialog(title,post_name,post_description,dialog_data,'post',messages,language=self.language,language_text=self.language_text)
            rc = dialog.ShowModal(Rhino.UI.RhinoEtoApp.MainWindow)
            if rc:
                if edit: del self.postprocessors[self.user_data['post']]
                new_settings = {}
                new_name = self.ValidateName(dialog.GetName(),self.postprocessors)
                new_settings['description'] = dialog.GetDescription()
                dialog_values = dialog.GetSettings('Code')
                for i in range(len(dialog_values)):
                    post_input = self.machining_input['POST_INPUT'][i]
                    if post_input['type'] == 'list': 
                        value = [e.strip() for e in dialog_values[i].split(',')]
                    elif post_input['type'] == 'number':
                        value = int(dialog_values[i])
                    else:
                        value = dialog_values[i].strip()
                    new_settings[post_input['var']] = value
                self.postprocessors.update({new_name:new_settings})
                self.user_data['post'] = new_name
                self.ConsoleLog('%s: %s' % (self.txt('Postprocesadores actualizados'),new_name))
                
                #Redraw dropdown
                self.UpdatePostDropdown()
                
        except Exception as e:
            print(e)
    
    
    def UpdatePostDropdown(self):
        self.dropdownlist.DataStore = sorted(self.postprocessors.keys())
        self.dropdownlist.SelectedIndex = sorted(self.postprocessors.keys()).index(self.user_data['post'])
    def UpdateSettingsDropdown(self):
        try:
            machining_settings = sorted(self.machining_settings.keys())
            
            if not self.user_data["selected_preset"]:
                self.user_data["selected_preset"] = machining_settings[0]
            
            preset_name = self.user_data["selected_preset"]
            preset_description = self.machining_settings[preset_name]['descripcion']
            self.dropdownlist_settings.DataStore =  machining_settings 
            self.dropdownlist_settings.SelectedIndex = machining_settings.index(self.user_data["selected_preset"])
            self.SelectedPresetText.Text = preset_description
        except Exception as e:
            print(e)
    
    def SelectFileName(self):
        
        path = self.user_data['file_path'] if self.user_data['file_path'] else rs.DocumentPath()
        name = self.user_data['file_name'] if self.user_data['file_name'] else rs.DocumentName().replace('.3dm','_gcode.nc') if rs.DocumentName() else '_gcode.nc'
        save_path = rs.SaveFileName(self.txt("Selecciona donde guardar el codigo"),None,path,name,".nc")
     
        if save_path:
             self.user_data["file_path"],self.user_data["file_name"] = os.path.split(save_path)
        return save_path      
    
    def CheckPreconditions(self):
        if not self.rhino_objects:
            self.ConsoleLog('Error: %s' % self.txt("No hay objetos seleccionados"))
            return False
        if not self.user_data['selected_preset']:
            self.ConsoleLog('Error: %s' % self.txt("No hay rutina seleccionada"))
            return False
        return True
    
    def SaveImages(self,file_path):
        save_path_2 = file_path.replace('.nc',"_top.png")
        save_path = file_path.replace('.nc',"_perspective.png")
        persp_view = "Perspective"
        top_view = "Top"
        desire_width = 1800
        views = rs.ViewNames()
        if views:
            persp_view = views[0]
            top_view = views[1]
            width,height = rs.ViewSize(persp_view)
            scale = int(desire_width/width)
            image_size = (width*scale,height*scale)
            rs.CreatePreviewImage(save_path, view=persp_view, size=image_size, flags=2, wireframe=False)
            width,height = rs.ViewSize(top_view)
            scale = int(desire_width/width)
            rs.CreatePreviewImage(save_path_2, view=top_view, size=image_size, flags=2, wireframe=False)
            return save_path,save_path_2
        return False
    # Create all of the functions used by controls
    
    def ExtractCeroPoint(self):
         #Gets cero point from rhino objects and deletes it from self list
        rhino_objects = self.rhino_objects
        if "cero_point" in rhino_objects.iterkeys():
            cero_point = rhino_objects["cero_point"]
            del rhino_objects["cero_point"]
        else: cero_point = (0,0,0)
        #Add tag to new cero
        dot = rs.AddTextDot("+",cero_point)
        rs.ObjectLayer(dot,self.layer_sorting)
        rs.ObjectColor(dot,(200,200,200))
        return cero_point,rhino_objects
    
    def GetModelObjects(self):
        model_objects = {}
        cero_point,rhino_objects = self.ExtractCeroPoint()
        for colorcode, objects in rhino_objects.iteritems():
            if objects:
                model_objects[colorcode] =[]
                preset = self.machining_settings[self.user_data["selected_preset"]]
                post = self.postprocessors[self.user_data['post']]
                general_settings = preset['cnc'] # or else use gooold --> self.general_settings
                for rh_object in objects:
                    if rs.IsObject(rh_object):
                        if colorcode == "points":
                            color = rs.ObjectColor(rh_object)
                            rgb = (rs.ColorRedValue(color),rs.ColorGreenValue(color),rs.ColorBlueValue(color))
                            if rgb == (0,255,0):
                                print('verde')
                            curve = g_curve(rh_object,preset["barrenado"],general_settings,0,False,cero_point,colorcode,post)
                        if colorcode == "curves_open":
                            curve = g_curve(rh_object,preset["grabado"],general_settings,0,False,cero_point,colorcode,post)
                        if colorcode == "curves_pocketing":
                            curve = g_curve(rh_object,preset["desbaste"],general_settings,-1,True,cero_point,colorcode,post)
                            #rs.ObjectLayer(curve.cut_curve,self.preview_layer_name)
                        if colorcode == "curves_outside":
                            curve = g_curve(rh_object,preset["corte"],general_settings,1,False,cero_point,colorcode,post)
                            #rs.ObjectLayer(curve.cut_curve,self.preview_layer_name)
                        if colorcode == "curves_inside":
                            curve = g_curve(rh_object,preset["corte"],general_settings,-1,False,cero_point,colorcode,post)
                            #rs.ObjectLayer(curve.cut_curve,self.preview_layer_name)
                        model_objects[colorcode].append(curve)
        return model_objects
    
    def GetSortedObjectsList(self):
        
        object_list = []
        for type,objects in self.model_objects.items():
            for obj in objects:
                point = obj.start_point
                object_list.append([obj,point[0],point[1]])
        return [i[0] for i in sorted(object_list, key = operator.itemgetter(2, 1))]
    
    def GetObjectsList(self):
        object_list = []
        for type,objects in self.model_objects.items():
            for obj in objects:
                object_list.append(obj)
        return object_list
    
    def GetRhinoNameList(self):
        try:
            object_list = []
            for type,objects in self.rhino_objects.items():
                if objects:
                    for obj in objects:
                        if rs.IsObject(obj): object_list.append(obj)
        
            return object_list
        except Exception as e: print(e)
    
    def SortClosest(self,rh_objects):

        closest_list = []
        test_object = rh_objects[0]
        closest_list.append(test_object)
        while True:
            if len(rh_objects) == 0:
                break
            rh_objects.pop(rh_objects.index(test_object))
            if len(rh_objects) == 0:
                break
            closest_point_index = rs.PointArrayClosestPoint([i.start_point for i in rh_objects],test_object.point)
            closest_object = rh_objects[closest_point_index]
            closest_list.append(closest_object)
            test_object = closest_object
        return closest_list

    
    def SortClusters(self,object_list):
        outside_curves = [obj for obj in object_list if obj.cam_type == 'curves_outside']
        test_curves = [obj for obj in object_list if obj.cam_type != 'curves_outside']     
        cluster_list = []
        count = 0
        for out_crv in outside_curves:
            
            for test_crv in test_curves:
                if rs.PointInPlanarClosedCurve(test_crv.point,out_crv.curve) and test_crv not in cluster_list:
                    cluster_list.append(test_crv)
                    test_crv.asignedcluster = count
                    out_crv.iscluster = True
            if out_crv.iscluster:
                out_crv.asignedcluster = count
                cluster_dot = rs.AddTextDot("%s: %s"% (self.txt('Pieza'),count),out_crv.point)
                rs.ObjectLayer(cluster_dot,self.layer_cluster)
                count+=1
            cluster_list.append(out_crv)
            
        for test_crv in test_curves:
            if test_crv not in cluster_list: cluster_list.append(test_crv)
        
        return cluster_list
    
    def GetGCodeString(self,object_list):
        gcode = []
        post = self.postprocessors[self.user_data['post']]
        if post["header"]: gcode += post["header"]
        
        general_settings = self.machining_settings[self.user_data["selected_preset"]]['cnc'] # or else use good old self.general_settings
        
        if post['spindle']: gcode.append('%s%s' % (post['spindle'],int(general_settings['spindle'])))
        gcode.append("%s Z%s %s%s" % (post['rapid'],general_settings["sec_plane"],post['feed'],int(general_settings["feed_rapid"])))

        for obj in object_list:
            gcode += obj.gcode
        if post["footer"]: gcode += post["footer"]
        return gcode
    
    def GetGCodeTime(self,object_list):
        gcode_time = 0
        last_point = False
        for obj in object_list:
            obj_time,last_point = obj.get_cut_time(last_point)
            gcode_time+= obj_time
        return round(gcode_time*60/100,2)
            
    def SetProgressBar(self,index):
        value = int(((index+1)*self.progressbar.MaxValue)/self.objects_count)
        if self.progressbar.Value != value:
            self.progressbar.Value = value    
            rs.Redraw()
        
    def SetObjectsByColor(self,objects):
        if not objects: return False
        points = []
        cero_point = False
        curves_inside = []
        curves_outside = []
        curves_open = []
        curves_pocketing = []
        curve_material = False
        obj_count = 0
        valid_objects = []
        for object in objects:
            if rs.IsCurve(object):
                color = rs.ObjectColor(object)
                rgb = (rs.ColorRedValue(color),rs.ColorGreenValue(color),rs.ColorBlueValue(color))
                if rs.IsCurveClosed(object):
                    if rgb == (0,0,255):
                        obj_count += 1
                        curves_inside.append(object)
                    if rgb == (255,0,0):
                        obj_count += 1
                        curves_outside.append(object)
                    if rgb == (255,0,255):
                        obj_count += 1
                        curves_pocketing.append(object)
                if rgb == (0,255,0):
                    obj_count += 1
                    curves_open.append(object)
                
                valid_objects.append(object)
            if rs.IsPoint(object):
                color = rs.ObjectColor(object)
                rgb = (rs.ColorRedValue(color),rs.ColorGreenValue(color),rs.ColorBlueValue(color))
                if rgb == (255,255,255):
                    cero_point = object
                else:
                    points.append(object)
                    obj_count += 1
                valid_objects.append(object)
                
        if obj_count:
            self.rhino_objects = {"points":points,"curves_open":curves_open,"curves_pocketing":curves_pocketing,"curves_inside":curves_inside,"curves_outside":curves_outside,"curve_material":curve_material}
            if cero_point: self.rhino_objects['cero_point'] = cero_point
        
        #Uncomment if using old selection method
        #self.SelectObjectsText.Text = '%s %s' % (obj_count, self.txt('Objetos agregados'))
        
        return valid_objects
    
    def make_code(self,sender,e):
        
        rgbobjs = self.SetObjectsByColor(rs.SelectedObjects())
        if not rgbobjs:
            self.ConsoleLog(self.txt('Error: Selecciona al menos una curva'))
            return 
        try:
            if not self.CheckPreconditions(): return
            file_path = self.SelectFileName()
            rs.EnableRedraw(False)
            self.AddPreviewLayers()
            
            self.model_objects = self.GetModelObjects()
            object_list = self.GetSortedObjectsList() if self.user_data['sorting'] else self.GetObjectsList()
            if self.user_data['sort_closest']: object_list = self.SortClosest(object_list)
            if self.user_data['autocluster']: object_list = self.SortClusters(object_list)
            self.objects_count = len(object_list)
            for obj in object_list:
                index = object_list.index(obj)
                sort_dot = rs.AddTextDot(str(index +1),obj.start_point)
                rs.ObjectLayer(sort_dot,self.layer_sorting)
                obj.process()
                rs.ObjectLayer(obj.preview,self.layer_preview)
                self.SetProgressBar(index)
            rs.EnableRedraw(True)
           
            if self.user_data['save_image']: self.SaveImages(file_path)
            gcode = '\n'.join(self.GetGCodeString(object_list))
            gcode_time = self.GetGCodeTime(object_list)
            with open(file_path,'w') as f:
                f.write(gcode)
            self.ConsoleLog('%s: %s' % (self.txt('Archivo guardado'),file_path))
            self.ConsoleLog('%s: %s %s' % (self.txt('Tiempo de corte aproximado'),gcode_time,self.txt('minutos')))
        except Exception as e:
            print(e)
            
    
    def edit_postprocessors(self,sender,e):
        self.CreatePostprocessor(edit=True)
        
    def new_postprocessors(self,sender,e):
        self.CreatePostprocessor()
        
    def delete_postprocessors(self,sender,e):
        try:
            post = self.user_data['post']
            if len(self.postprocessors.keys()) == 1:
                self.ConsoleLog(self.txt('Debe existir al menos un postprocesador'))
                return
            if rs.MessageBox("%s %s" % (self.txt('Borrar'),post), 4 | 32) == 6:
                del self.postprocessors[post]
                self.user_data['post'] = sorted(self.postprocessors.keys())[0]
                self.UpdatePostDropdown()
                self.ConsoleLog('%s: %s' % (self.txt('Rutina borrada'),post))
        except Exception as e:
            print(e)
    def set_postprocessor(self,sender,e):
        self.user_data['post']  = sorted(self.postprocessors.keys())[self.dropdownlist.SelectedIndex]
    def set_machining_settings(self,sender,e):
        self.user_data["selected_preset"] = self.dropdownlist_settings.DataStore[self.dropdownlist_settings.SelectedIndex] if self.dropdownlist_settings.DataStore else None
        self.UpdateSettingsDropdown()
    def set_general_settings(self,sender,e):
        for name,value in self.general_inputs.items():
            self.general_settings[name] = value['input'].Value
            
    def set_user_data(self,sender,e):
        for name,value in self.checkbox_inputs.items():
            self.user_data[name] = True if value.Checked else False
    
    def edit_settings(self,sender,e):
        if not self.user_data["selected_preset"]: return
        self.CreateSettings(edit=True)
        self.UpdateSettingsDropdown()
    
    def new_settings(self,sender,e):
        try:
            self.CreateSettings(edit=False)
            self.UpdateSettingsDropdown()
        except Exception as e:
            print(traceback.format_exc())
        

    def delete_settings(self,sender,e):

        preset = self.user_data["selected_preset"]
        if not preset: return
        if rs.MessageBox("%s %s" % (self.txt('Borrar'),preset), 4 | 32) == 6:
            del self.machining_settings[preset] 
            self.user_data['selected_preset'] = False
            
            #self.SelectSettingsText.Text =  self.txt('Sin rutina')
            self.ConsoleLog('%s: %s' % (self.txt('Rutina borrada'),preset))
            self.UpdateSettingsDropdown()

    def select_preset(self,sender,e):
        
        preset =  rs.ListBox(sorted(["* %s"%i if self.machining_settings[i]["persistant"] else "%s"%i for i in self.machining_settings]), message=self.txt("Rutinas"), title=self.txt("Cambiar rutina"), default=None)
        if preset:
            self.user_data["selected_preset"] = preset.replace("*","").strip()
            self.SelectSettingsText.Text = preset
            self.SelectSettingsDescription.Text = self.machining_settings[self.user_data['selected_preset']]['descripcion']
    
    def select_objects(self,sender, e):

        self.SelectObjectsText.Text = self.txt("Selecciona curvas y puntos")
        objects = rs.GetObjects(self.txt("Selecciona curvas y puntos"),filter=7, group=False, preselect=True,select=True)
        if not objects:
            self.rhino_objects = []
            self.SelectObjectsText.Text = self.txt('Sin objectos')
            return
        self.SetObjectsByColor(objects)
       
        
    ## End of Dialog Class ##

class editDialog(forms.Dialog[bool]):

    # Dialog box Class initializer
    def __init__(self,title,name,description,settings,type=False,messages=False,persistant=False,language=False,language_text=False):
        
        #Set language settings for translation
        self.language = language
        self.language_text = language_text
        
        # Initialize dialog box
        self.Title = title
        self.Padding = drawing.Padding(10)
        self.Resizable = True
        
        # Create a table layout and add all the controls
        layout = forms.DynamicLayout()
        layout.Spacing = drawing.Size(5, 5)
        
        # Create name layout 
        name_layout = forms.DynamicLayout()
        name_layout.Spacing = drawing.Size(5, 5)
        # Create name input
        name_label = forms.Label(Text = '%s:' % self.txt('Nombre'))
        self.name_textbox = forms.TextBox(Text = name)
         # Create text input
        description_label = forms.Label(Text = '%s:' % self.txt('Descripcion'))
        self.description_textarea = forms.TextArea(Text = description)
        self.description_textarea.Size = drawing.Size(-1, 50)
        # Add name and input to layout
        name_layout.AddRow(name_label,self.name_textbox)
        name_layout.AddRow(description_label,self.description_textarea)
        # Create grid layout 
        grid_layout = forms.DynamicLayout()
        grid_layout.Spacing = drawing.Size(5, 5)
        # Create GridView
        self.grid_settings = {}
        labels = []
        grids = []
        for s_name, s_values in settings.items():
            settings_label = forms.Label(Text = '%s:' % self.txt(s_name))
            settings_grid = self.CreateGrid(s_values)
            labels.append(settings_label)
            grids.append(settings_grid)
            #grid_layout.AddRow(settings_label)
            #grid_layout.AddRow(settings_grid)
            self.grid_settings[s_name] = settings_grid
        grid_layout.AddRow(tuple(labels))
        grid_layout.AddRow(tuple(grids))
        
         # Create layout for the button
        button_layout = forms.DynamicLayout()
        button_layout.Spacing = drawing.Size(5, 5)
         # Create the default button
        self.DefaultButton = forms.Button(Text = self.txt('Guardar'))
        self.DefaultButton.Click += self.OnOKButtonClick
        # Create the abort button
        self.AbortButton = forms.Button(Text =  self.txt('Cancelar'))
        self.AbortButton.Click += self.OnCloseButtonClick
        
        if type == 'preset':
            self.radiobuttonlist = forms.RadioButtonList()
            self.radiobuttonlist.DataStore = [self.txt('Guardar localmente'), self.txt('Solo en este archivo de Rhino')]
            self.radiobuttonlist.Orientation = forms.Orientation.Vertical
            self.radiobuttonlist.SelectedIndex = persistant if persistant else 0
            # Add button to layout
            button_layout.AddRow(self.radiobuttonlist,None,self.DefaultButton, self.AbortButton)
        elif type == 'post':
            button_layout.AddRow(None,self.DefaultButton, self.AbortButton)
         # Create controls for the dialog
        layout.AddRow(name_layout)
        layout.AddRow(None)
        layout.AddRow(None)
        layout.AddRow(grid_layout)
        
         # Add messages if required
        if messages:
            layout.AddRow(None)
            layout.AddRow(None)
            for message in messages:
                layout.AddRow(forms.Label(Text = self.txt(message)))
           
        layout.AddRow(None)
        layout.AddRow(None)
        layout.AddRow(button_layout)
       
        # Set the dialog content
        self.Content = layout

    def CreateGrid(self,values):
        
        gridview = forms.GridView()
        
        gridview.ShowHeader = False
        gridview.DataStore = (values)
        
        column1 = forms.GridColumn()
        column1.Editable = False
        column1.DataCell = forms.TextBoxCell(0)
        gridview.Columns.Add(column1)

        column2 = forms.GridColumn()
        column2.Editable = True
        column2.DataCell = forms.TextBoxCell(1)
        gridview.Columns.Add(column2)
        
        return gridview

    # Start of the class functions

    # Close button click handler
    def OnCloseButtonClick(self, sender, e):
        self.Close(False)

    # OK button click handler
    def OnOKButtonClick(self, sender, e):
        self.Close(True)
    
    # Return grid setting values 
    
    def GetSettings(self,grid_name):
        return [i[1] for i in self.grid_settings[grid_name].DataStore]
    
    def SaveLocally(self):
        return self.radiobuttonlist.SelectedIndex

    def GetName(self):
        return self.name_textbox.Text.strip()
    def GetDescription(self):
        return self.description_textarea.Text
    def txt(self,txt):
        
        #Translates text if necessary
        if txt not in self.language_text:
            self.language_text[txt] = {'English':''}
        if self.language != 'Espanol' and self.language not in self.language_text[txt]:
            self.language_text[txt][self.language] = ''
        if self.language == 'Espanol' or not self.language_text[txt][self.language]:
            return txt
        else:
            return self.language_text[txt][self.language]
    ## End of Dialog Class ##

class g_curve():    
    def __init__(self,curve,input_data,general_input,compensation,pocketing,cero_point,cam_type=False,post=False):
        #Initial needed values
        self.input_data = input_data
        self.general_input = general_input
        self.compensation = compensation
        self.pocketing = pocketing
        self.curve  = curve #Original curve nothing modifies it, the self.nurbs_curve is used.
        self.nurbs_curve  = curve
        self.cero_point = cero_point
        self.cam_type = cam_type
        self.post = post if post else self.get_default_post()
        #Calculated outside values
        self.asignedcluster = -1
        self.iscluster = False
        #Some other values
        self.color_palette = {"cut":(153,204,255),"plunge":(254,184,0),"point":(153,204,255),"rapid":(200,200,200)}
        self.geometry_type = "point"  if rs.IsPoint(self.nurbs_curve) else "curve" if rs.IsCurveClosed(self.nurbs_curve) else "open_curve" 
        self.point = self.curve if rs.IsPoint(self.nurbs_curve) else rs.CurveAreaCentroid(self.nurbs_curve)[0] if rs.IsCurveClosed(self.nurbs_curve) else rs.CurveStartPoint(self.nurbs_curve)   # Centroide curva original
        self.start_point = rs.PointCoordinates(self.nurbs_curve,False) if rs.IsPoint(self.nurbs_curve) else rs.CurveStartPoint(self.nurbs_curve)
        self.cut_curve = self.get_cut_curve()
        self.gcode_points = []
        self.time = 0
        
    def get_default_post(self):
        return {
            "footer": [
                "M5"
            ], 
            "feed": "F", 
            "description": "Arduino GRBL\r\nTinyG ", 
            "round_tol": 2, 
            "cut": "G01", 
            "spindle": "", 
            "rapid": "G00", 
            "header": [
                "G21", 
                "G90", 
                "G54", 
                "M3"
            ]
        }
    
    def round_point(self,point):
        return (round(point[0],self.post['round_tol']),round(point[1],self.post['round_tol']),round(point[2],self.post['round_tol'])) 
    
    def process(self):
        
        if rs.IsPoint(self.nurbs_curve):
            self.preview = self.get_cut_path_point(self.cut_curve)
        elif self.compensation == 0:# and not rs.IsCurveClosed(self.nurbs_curve):
            self.preview =  self.get_cut_path_open(self.cut_curve) 

        else:
            if self.input_data["finish_pass"] and not self.input_data["finish_entries"]:
                #Creates a finishing pass on the last level
                self.preview =  self.get_cut_path_closed(self.cut_curve,finish_pass=self.input_data["finish_pass"])
            elif self.input_data["finish_pass"]:
                #Creates a finishing pass equal to the cut curve but with a different offset
                 crv_finish_offset = self.get_cut_curve(self.compensation,(self.general_input['cut_diam']*.5)+self.input_data["finish_pass"])
                 self.preview =  self.get_cut_path_closed(crv_finish_offset)
                 self.preview += self.get_cut_path_closed(self.cut_curve,no_entries=self.input_data["finish_entries"],plunge_distance=False,omit_box=True)
            else:
                self.preview = self.get_cut_path_closed(self.cut_curve)
                
        self.gcode = self.get_g_code(self.preview,self.cero_point)
  
    def rgb_state(self,crv):
        
        crv_rgb = (rs.ColorRedValue(rs.ObjectColor(crv)),rs.ColorGreenValue(rs.ObjectColor(crv)),rs.ColorBlueValue(rs.ObjectColor(crv)))
        if crv_rgb == self.color_palette["cut"]:
            return 'cut'
        elif crv_rgb == self.color_palette["plunge"]:
            return 'plunge'
        elif crv_rgb == self.color_palette["rapid"]:
            return 'rapid'
    
    def get_g_code(self,crv_list,cero_point=False):
        if cero_point:
            for mcrv in crv_list:
                start = cero_point
                end = (0,0,0)
                rs.MoveObjects(mcrv,rs.VectorCreate(end,start))
                
        gcode = []
        gcode_points = []
        #Points do not have plunge
        if not rs.IsPoint(self.nurbs_curve):
            feed_plunge = self.input_data['feed_plunge']
            feed_rapid = self.general_input["feed_rapid"]
            feed_cut = self.input_data["feed_cut"]
        else:
            feed_plunge = self.input_data['feed']
            feed_rapid = self.general_input["feed_rapid"]
            feed_cut = self.input_data["feed"]
        
        #Creates the G0Hello and the first cut point and extracts the first cutting curve
        hello_pt = self.round_point(rs.CurveStartPoint(crv_list[0]))
        #gcode.append("(1)")
        gcode.append("%s X%sY%sZ%s %s%s" % (self.post['rapid'],hello_pt[0],hello_pt[1],hello_pt[2],self.post['feed'],int(feed_rapid)))
        #Attach the feed and the hello point to the list of points.
        gcode_points.append({'feed':int(feed_rapid),'point':hello_pt})
        
        state = self.rgb_state(crv_list[0])
        start_cut_pt = self.round_point(rs.CurveEndPoint(crv_list[0]))
        #gcode.append("(2)")
        gcode.append("%s Z%s %s%s" % (self.post['cut'],start_cut_pt[2],self.post['feed'],int(feed_plunge)))
        gcode_points.append({'feed':int(feed_plunge),'point':start_cut_pt})
        crvs_list = crv_list[1:]
        #reviews each block of curves 
        last_state = state
        
        for crv in crvs_list: 
            state = self.rgb_state(crv)
            if state == "cut":
                new_state = "cut"
                current_feed = feed_cut
                prefix = self.post['cut']
            elif  state == "plunge":
                new_state = "plunge"  
                current_feed = feed_plunge
                prefix = self.post['cut']
            elif state == "rapid":
                new_state = "rapid"
                current_feed = feed_rapid
                prefix = self.post['rapid']
  
            add_feed = True if new_state != last_state else False
            last_state = new_state
           
            curve_segments = rs.ExplodeCurves(crv, delete_input=False)
            if not curve_segments: curve_segments = [rs.CopyObject(crv)]
            #check each segment on the curve to see if it is an arc or line etc. and assign code per point 
            for crv in curve_segments:
                crv_gcode = []
                if rs.IsCircle(crv):
                    atol=sc.doc.ModelAngleToleranceDegrees
                    cir_ctr = self.round_point(rs.CircleCenterPoint(crv))
                    cir_Start = self.round_point(rs.CurveStartPoint(crv))
                    ref_plane=rs.ViewCPlane()
                    arc_crv=rs.coercecurve(crv)
                    rc,arc=arc_crv.TryGetArc()
                    arc_plane = arc.Plane
                    delta_ptx = cir_ctr[0] - cir_Start[0] 
                    delta_pty = cir_ctr[1] - cir_Start[1]
                    angle=rs.VectorAngle(ref_plane.Normal,arc_plane.Normal)
                    if Rhino.RhinoMath.EpsilonEquals(angle,180,atol): arc_dir="G02" #clockwise
                    elif Rhino.RhinoMath.EpsilonEquals(angle,0,atol): arc_dir="G03" #counterclockwise
                    #crv_gcode.append("(3)")
                    crv_gcode.append("%s I%sJ%s %s%s" % (arc_dir,delta_ptx,delta_pty,self.post['feed'],int(current_feed)))
                elif rs.IsArc(crv):
                    atol=sc.doc.ModelAngleToleranceDegrees
                    cir_ctr = self.round_point(rs.ArcCenterPoint(crv))
                    cir_Start = self.round_point(rs.CurveStartPoint(crv))
                    cir_End = self.round_point(rs.CurveEndPoint(crv))
                    ref_plane=rs.ViewCPlane()
                    arc_crv=rs.coercecurve(crv)
                    rc,arc=arc_crv.TryGetArc()
                    arc_plane = arc.Plane
                    delta_ptx = cir_ctr[0] - cir_Start[0] 
                    delta_pty = cir_ctr[1] - cir_Start[1]
                    angle=rs.VectorAngle(ref_plane.Normal,arc_plane.Normal)
                    if Rhino.RhinoMath.EpsilonEquals(angle,180,atol): arc_dir="G02" #clockwise
                    elif Rhino.RhinoMath.EpsilonEquals(angle,0,atol): arc_dir="G03" #counterclockwise
                    #crv_gcode.append("(4)")
                    crv_gcode.append("%s X%sY%s I%sJ%s %s%s" % (arc_dir,cir_End[0],cir_End[1],delta_ptx,delta_pty,self.post['feed'],int(current_feed)))                    
                    
                    #crv_gcode.append("%s X%sY%sZ%s %s%s" % (prefix,crv_endpt[0],crv_endpt[1],crv_endpt[2],self.post['feed'],int(current_feed)))
                elif rs.IsLine(crv) or rs.CurveLength(crv)<self.general_input['tolerance']: # If the line is straight
                    crv_endpt = self.round_point(rs.CurveEndPoint(crv))
                    if curve_segments.index(crv) == 0 and add_feed:  #if there is a change of state between plunge and cut and it is the first line add the feed variable
                        #crv_gcode.append("(5)")
                        crv_gcode.append("%s X%sY%sZ%s %s%s" % (prefix,crv_endpt[0],crv_endpt[1],crv_endpt[2],self.post['feed'],int(current_feed)))
                    else:
                        #crv_gcode.append("(6)")
                        
                        #crv_gcode.append("%s X%sY%sZ%s" % (self.post['rapid'],crv_endpt[0],crv_endpt[1],crv_endpt[2]))
                        #crv_gcode.append("X%sY%sZ%s" % (crv_endpt[0],crv_endpt[1],crv_endpt[2]))
                        crv_gcode.append("%s X%sY%sZ%s %s%s" % (prefix,crv_endpt[0],crv_endpt[1],crv_endpt[2],self.post['feed'],int(current_feed)))
                        
                    gcode_points.append({'feed':int(current_feed),'point':crv_endpt})
                else:
                    no_points = int(rs.CurveLength(crv)/self.general_input['tolerance'])
                    pts = rs.DivideCurve(crv,no_points, create_points=False, return_points=True)[1:]
                    
                    if rs.IsCurveClosed(crv):
                        pts.append(rs.CurveStartPoint(crv))
                    #crv_gcode.append("(7)")
                    fst_pnt = self.round_point(pts[0])
                    crv_gcode.append("%s X%sY%sZ%s %s%s" % (prefix,fst_pnt[0],fst_pnt[1],fst_pnt[2],self.post['feed'],int(current_feed)))
                    for pt in pts:
                        if curve_segments.index(crv) == 0 and pts.index(pt) == 0 and add_feed:  #if there is a change of state between plunge and cut and it is the first line add the feed variable
                            pt = self.round_point(pt)
                            crv_gcode.append("(8)")
                            crv_gcode.append("%s X%sY%sZ%s %s%s" % (prefix,pt[0],pt[1],pt[2],self.post['feed'],int(current_feed)))
                        else:
                            pt = self.round_point(pt)
                            crv_gcode.append("(9)")
                            crv_gcode.append("X%sY%sZ%s" % (pt[0],pt[1],pt[2]))
                            
                        gcode_points.append({'feed':int(current_feed),'point':pt})
                           
                gcode += crv_gcode
                rs.DeleteObject(crv)
                
        if cero_point:
            for mcrv in crv_list:
                start = cero_point
                end = (0,0,0)
                rs.MoveObjects(mcrv,rs.VectorCreate(start,end))
        
        self.gcode_points = gcode_points     
        return gcode
    
    def get_cut_time(self,last_point = False):
        if not self.gcode_points: return
        gcode_time = 0
        points = self.gcode_points if not last_point else [last_point]+self.gcode_points
        for i in range(len(points)-1):
            point1 = points[i]['point']
            point2 = points[i+1]['point']
            feed = points[i+1]['feed']
            distance = rs.Distance(point1,point2)
            gcode_time += distance/feed
        return [gcode_time,points[-1]]  
    
    def get_cut_path_point(self,point):
        o_point = point
        point = rs.PointCoordinates(o_point)
        no_entries = self.input_data["entries"]
        level_depth = self.input_data["depth"] / no_entries
        sec_plane = self.general_input["sec_plane"]
        #Final operating checklist for curve cutter
        curves_cut_path = []
    
        start_point = (point[0],point[1],point[2]+2)
        hello_line = rs.AddLine((point[0],point[1],sec_plane),start_point)
        rs.ObjectColor(hello_line,self.color_palette["cut"])
        curves_cut_path.append(hello_line)
        
        for entrie in range(1,int(no_entries)+1):
            end_point = (point[0],point[1],entrie*level_depth)
            in_line = rs.AddLine(start_point,end_point)
            out_line = rs.AddLine(end_point,start_point)
            rs.ObjectColor([in_line,out_line],self.color_palette["cut"])
            curves_cut_path += [in_line,out_line]
            
        end_line = rs.AddLine(start_point,(point[0],point[1],sec_plane))
        rs.ObjectColor(end_line,self.color_palette["cut"])
        curves_cut_path.append(end_line)
        rs.DeleteObject(o_point)
        return curves_cut_path
             
    def get_cut_path_open(self,crv):
        
        no_entries = self.input_data["entries"]
        level_depth = self.input_data["depth"]/ no_entries
        sec_plane = self.general_input["sec_plane"]
        #Final operating checklist for curve cutter
        curves_cut_path = [] 
        
        for entrie in range(1,int(no_entries)+1):
 
            translation = rs.VectorAdd((0,0,0),(0,0,level_depth*entrie))
            level_curve = rs.CopyObject(crv,translation)
            rs.ObjectColor(level_curve,self.color_palette["cut"])
            if entrie % 2 == 0: rs.ReverseCurve(level_curve)
            if entrie == 1:
                entry_end_point = rs.CurveStartPoint(level_curve)
                in_curve = rs.AddLine((entry_end_point[0],entry_end_point[1],sec_plane),entry_end_point)
                rs.ObjectColor(in_curve,self.color_palette["plunge"])
                curves_cut_path.append(in_curve)
            
            curves_cut_path.append(level_curve)
            
            if entrie < no_entries:
                level_ept = rs.CurveEndPoint(level_curve)
                plunge_curve = rs.AddLine(level_ept,(level_ept[0],level_ept[1],(entrie+1)*level_depth))
                rs.ObjectColor(plunge_curve,self.color_palette["plunge"])
                curves_cut_path.append(plunge_curve)
            
            
        final_point = rs.CurveEndPoint(level_curve)
        out_curve = rs.AddLine(final_point,(final_point[0],final_point[1],sec_plane))
        rs.ObjectColor(out_curve,self.color_palette["cut"])
        curves_cut_path.append(out_curve)
        
        rs.DeleteObjects([crv])
        
        return curves_cut_path
   
    def isCurveNew(self,offsets,curve):
        if offsets:
            for offset in offsets:
                if rs.Distance(rs.CurveStartPoint(offset),rs.CurveStartPoint(curve))==0:
                    return False
        return True
    
    def getSmall(self,curve_1,curve_2):
        if self.isSmall(curve_1, curve_2):
            return curve_1
        else:
            return curve_2    
    
    def isSmall(self,curve_1,curve_2):
        if rs.CurveArea(curve_1) < rs.CurveArea(curve_2):
            return  True
        else:
            return False
    
    def OffsetCurve(self,level_cut):
        
        check_presision = 10
        offset_type=3
        mini_test_offset = 0.3
        branched_curves = []
        main_curve = level_cut
        
        offset_distance = self.general_input["cut_diam"] * self.input_data["xy_dist"]
        curve_1 = rs.OffsetCurve(main_curve,rs.CurveAreaCentroid(main_curve)[0],-mini_test_offset,None,offset_type)
        curve_2 = rs.OffsetCurve(main_curve,rs.CurveAreaCentroid(main_curve)[0],mini_test_offset,None,offset_type)
        
        if curve_1 and curve_2:
            if len(curve_1) != 1 or len(curve_2) != 1:
                rs.DeleteObjects(curve_1)
                rs.DeleteObjects(curve_2)
                return branched_curves
        
        mini_test = self.getSmall(curve_1, curve_2)
        do_points = rs.DivideCurve(mini_test,check_presision,False)
        rs.DeleteObjects([curve_1,curve_2])
        do_points.append(rs.CurveAreaCentroid(main_curve)[0])
        
        for i in range(0,len(do_points)):
            new_offset_curve = rs.OffsetCurve(main_curve,do_points[i],offset_distance,None,offset_type)
            try:
                if self.isCurveNew(branched_curves, new_offset_curve) and rs.IsCurveClosed(new_offset_curve) and self.isSmall(new_offset_curve, main_curve):
                    branched_curves.append(new_offset_curve)
                else:
                    rs.DeleteObject(new_offset_curve)
            except:
                if new_offset_curve:
                    rs.DeleteObjects(new_offset_curve)        
        
        for curve in branched_curves:
            rs.ObjectColor(curve,self.color_palette["cut"])
            
        if not branched_curves or len(branched_curves) > 1:
            branched_curves.append("sec_plane")
            
        return branched_curves
    
    def get_pocketing_crvs_circular(self,crv):
        
        cut_curve = self.get_cut_curve(self.compensation, self.general_input['cut_diam']*.4,crv)
        
        centroid = rs.CurveAreaCentroid(cut_curve)[0]
        offset_distance = self.general_input["cut_diam"] * self.input_data["xy_dist"]
        radius = offset_distance
        
        start_line = rs.AddLine(rs.CurveEndPoint(crv),rs.CurveStartPoint(cut_curve))
        end_line = rs.AddLine(rs.CurveStartPoint(cut_curve),rs.CurveEndPoint(crv))
        
        pocket_perimeter = [start_line,cut_curve,end_line]
        pocket_circles = []
        pocket_curves = []
        
        valid_circle = True
        reverse = False
        while valid_circle:
            circle = rs.AddCircle(centroid,radius)
            if not reverse:
                reverse = True
            else:
                reverse = False
                rs.ReverseCurve(circle)
            
            if rs.IsCircle(crv):
                seam_start_point = rs.CurveClosestObject(circle,start_line)[1]
            else:
                seam_start_point = rs.CurveClosestObject(circle,cut_curve)[1]
                
            rs.CurveSeam(circle,rs.CurveClosestPoint(circle,seam_start_point))
            intersection_list = rs.CurveCurveIntersection(circle,cut_curve)
            if intersection_list:
                segments = rs.SplitCurve(circle,[i[5] for i in intersection_list])
                cluster_curves = []
                for s in segments:
                    if not rs.PointInPlanarClosedCurve(rs.CurveMidPoint(s),cut_curve):
                        rs.DeleteObject(s)
                    else:
                        pocket_curves.append(s)
                        cluster_curves.append(s)
            else:
                containment = rs.PlanarClosedCurveContainment(circle,cut_curve)
                if not containment: rs.DeleteObject(circle)
                elif containment == 3: 
                    rs.DeleteObject(circle)
                    valid_circle = False
                else:
                    if pocket_circles:
                        circle_connection = rs.AddLine(rs.CurveEndPoint(circle),rs.CurveStartPoint(pocket_circles[-1]))
                        pocket_circles.append(circle_connection)
                    pocket_circles.append(circle)
            radius += offset_distance
            
        if pocket_circles:
            if rs.IsCircle(crv): # Revisa si es circulo
                sp,ep = rs.CurveClosestObject(pocket_circles[-1],start_line)[1:]
            else:
                sp,ep = rs.CurveClosestObject(pocket_circles[-1],cut_curve)[1:]
            pocket_circles.append(rs.AddLine(sp,ep))
        
        pocket_clusters = self.create_pocket_clusters(pocket_curves,crv,offset_distance*4) if pocket_curves else []
        pocket_circles.reverse()
        return [pocket_perimeter,pocket_clusters,pocket_circles]

    def create_pocket_clusters(self,pocket_curves,crv,max_length):
        joined_pocket_curves = []
        for i in range(len(pocket_curves)):
            pocket_curve = pocket_curves[i]
            joined_pocket_curves.append(pocket_curve)
            sample_curves = pocket_curves[i+1:]
            if sample_curves:
                closest_curve = rs.CurveClosestObject(pocket_curve,sample_curves)[0] if len(sample_curves) != 1 else sample_curves[0]
                connection_line = rs.AddLine(rs.CurveEndPoint(pocket_curve),rs.CurveStartPoint(closest_curve))
                if rs.CurveLength(connection_line) < max_length and not rs.CurveCurveIntersection(connection_line,crv):
                    joined_pocket_curves.append(connection_line)
                else:
                    rs.DeleteObject(connection_line)   
        clusters = rs.JoinCurves(joined_pocket_curves,delete_input=True)
        return clusters
        
    def pocket_path_circular(self,cep,translation,pocket_list):
        
        def jump(pt1,pt2,height,color_palette):
            up_curve = rs.AddLine(pt1,(pt1[0],pt1[1],height))
            go_curve = rs.AddLine((pt1[0],pt1[1],height),(pt2[0],pt2[1],height))
            down_curve = rs.AddLine((pt2[0],pt2[1],height),pt2)
            rs.ObjectColor(up_curve,color_palette["rapid"])
            rs.ObjectColor(go_curve,color_palette["rapid"])
            rs.ObjectColor(down_curve,color_palette["rapid"])
            return [up_curve,go_curve,down_curve]
        
        def copy_into_level(crvs,translation,color_palette):
            level_crvs = []
            for crv in crvs:
                new_crv = rs.CopyObject(crv,translation)
                rs.ObjectColor(new_crv,color_palette["cut"])
                level_crvs.append(new_crv)
            return level_crvs
        
        sec_plane = self.general_input['sec_plane']
        pocket_perimeter,pocket_clusters,pocket_circles = [copy_into_level(i,translation,self.color_palette) for i in pocket_list]
        
        pocket_path = []
        
        pocket_path += pocket_perimeter[:-1]
        
        if rs.CurveEndPoint(pocket_perimeter[0]) != rs.CurveStartPoint(pocket_circles[0]): # Revisa si es circulo
            pocket_path += jump(rs.CurveEndPoint(pocket_perimeter[0]),rs.CurveStartPoint(pocket_circles[0]),sec_plane,self.color_palette)
        pocket_path += pocket_circles
        
        if pocket_clusters: # Check if it is a circle
            pocket_path += jump(rs.CurveEndPoint(pocket_circles[-1]),rs.CurveStartPoint(pocket_clusters[0]),sec_plane,self.color_palette)
            for i,path in enumerate(pocket_clusters):
                pocket_path.append(path)
                if i < len(pocket_clusters)-1:
                    pocket_path += jump(rs.CurveEndPoint(path),rs.CurveStartPoint(pocket_clusters[i+1]), sec_plane, self.color_palette)
            pocket_path += jump(rs.CurveEndPoint(pocket_clusters[-1]),rs.CurveStartPoint(pocket_perimeter[-1]), sec_plane, self.color_palette)
        
        pocket_path.append(pocket_perimeter[-1])
        
        return pocket_path
        
    
    def get_pocketing_crvs_offset(self,crv):
        crv_pocket = self.make_pocket_curves(crv)
        if crv_pocket[0] != "sec_plane":
            return self.finish_pocket_curves(crv_pocket)
    
    def make_pocket_curves(self,level_cut):
        #
        cut_curves = []
        offset_curves = self.OffsetCurve(level_cut)
        if offset_curves:
            for offset_curve in offset_curves:
                cut_curves.append(offset_curve)
                if offset_curve != "sec_plane":
                    deep_curve = self.make_pocket_curves(offset_curve)
                    if deep_curve:
                        cut_curves += deep_curve
            
            return cut_curves
        else:
            return False
    
    def finish_pocket_curves(self,crv_list):
        
        block_curves = []
        for i in range(0,len(crv_list)):
            if i == 0:
                pep = rs.CurveEndPoint(self.cut_curve)
                csp = rs.CurveStartPoint(crv_list[i])
                join_line = rs.AddLine(pep,csp)
                rs.ObjectColor(join_line,self.color_palette["cut"])
                block_curves.append(join_line)
                
            crv = crv_list[i]
            if crv == "sec_plane":
                block_curves.append(crv)
            else:
                try:
                    if i<len(crv_list) and crv_list[i+1] != "sec_plane":
                        nsp = rs.CurveStartPoint(crv_list[i+1])
                        cep = rs.CurveEndPoint(crv_list[i])
                        join_line = rs.AddLine(cep,nsp)
                        rs.ObjectColor(join_line,self.color_palette["cut"])
                        block_curves.append(crv_list[i])
                        block_curves.append(join_line)
                    else:
                        block_curves.append(crv)
                except:
                    pass
        return block_curves
                                      
    def get_cut_path_closed(self,main_crv,no_entries=False,plunge_distance=False,finish_pass=False,omit_box=False):
        
        if finish_pass: crv = self.get_cut_curve(compensation=self.compensation,offset_distance=finish_pass,nurbs_curve=main_crv)
        else: crv = main_crv
        
        #creates the cutting curve and the plunge curve at the original level
        plunge_distance = self.input_data["plunge"] if not plunge_distance else plunge_distance
        no_entries = no_entries if no_entries else self.input_data["entries"]
        level_depth = self.input_data["depth"]/ no_entries
        crv_domain = rs.CurveDomain(crv)
        crv_length = rs.CurveLength(crv)
        if plunge_distance >= crv_length: plunge_distance = crv_length*.8
        
        plunge_end_point = rs.DivideCurveLength(crv, plunge_distance, create_points=False, return_points=True)[1]
        split_param = rs.CurveClosestPoint(crv,plunge_end_point)
        planar_plunge_crv,cut_crv = rs.SplitCurve(rs.CopyObject(crv),split_param)
        
        #crv_domain_param = crv_domain[1]-crv_domain[0]
        #trim_domain =  (plunge_distance*crv_domain_param)/crv_length
        #planar_plunge_crv,cut_crv = rs.SplitCurve(rs.CopyObject(crv),rs.CurveDomain(crv)[0]+trim_domain)
        
        no_points = int(rs.CurveLength(planar_plunge_crv)/self.general_input['tolerance'])
        if not no_points: 
            no_points =1
        
        plunge_pts = rs.DivideCurve(planar_plunge_crv,no_points, create_points=False, return_points=True)
        plunge_moved_pts = []
        z_count = abs(level_depth)
        z_pass = abs(level_depth/no_points)
        for pt in plunge_pts:
            new_point = pt[0],pt[1],pt[2]+z_count
            plunge_moved_pts.append(new_point)
            z_count -= z_pass
            
        plunge_crv = rs.AddPolyline(plunge_moved_pts)
        rs.SimplifyCurve(plunge_crv)
        
        #Creates cutting curves for pocketing if required
        if self.pocketing and not omit_box:
            if self.input_data["circular_pocketing"]:
                pocketing_crvs = self.get_pocketing_crvs_circular(crv)
                self.pocketing = False if not pocketing_crvs else self.pocketing
            else:
                pocketing_crvs = self.get_pocketing_crvs_offset(crv)
                self.pocketing = False if not pocketing_crvs else self.pocketing
       
        #Final operating checklist for curve cutter
        curves_cut_path = [] 
        
        #adds cutter input
        entry_end_point = rs.CurveStartPoint(planar_plunge_crv)
        sec_plane = self.general_input["sec_plane"]
        in_curve = rs.AddLine((entry_end_point[0],entry_end_point[1],sec_plane),entry_end_point)
    
        domain = rs.CurveDomain(in_curve)
        parameter = domain[1] * .8
        in_curve_rapid,in_curve_plunge = rs.SplitCurve(in_curve,parameter, delete_input=True)
        
        rs.ObjectColor(in_curve_rapid,self.color_palette["rapid"])
        curves_cut_path.append(in_curve_rapid)
        rs.ObjectColor(in_curve_plunge,self.color_palette["plunge"])
        curves_cut_path.append(in_curve_plunge)
        
        
        #general list of curves and sorts them by level, differentiating between plunge and cut by color.
        for entrie in range(1,int(no_entries)+1):
            z_level = level_depth*entrie
            translation = rs.VectorAdd((0,0,0),(0,0,z_level))
            level_plunge= rs.CopyObject(plunge_crv,translation)
            level_cut = rs.CopyObject(cut_crv,translation)
            rs.ObjectColor(level_plunge,self.color_palette["plunge"])
            rs.ObjectColor(level_cut,self.color_palette["cut"])
            curves_cut_path.append(level_plunge)
            curves_cut_path.append(level_cut)
            if self.pocketing and not omit_box and pocketing_crvs:
                if self.input_data["circular_pocketing"]:
                    pocket_path = self.pocket_path_circular(rs.CurveEndPoint(level_cut),translation,pocketing_crvs)
                else:
                    pocket_path = self.pocket_path_offset(z_level,translation,pocketing_crvs)
                curves_cut_path += pocket_path
                
        #add the last cut line as a plunge to avoid generating such an abrupt piece bounce.
        #final_cut = rs.CopyObject(planar_plunge_crv,translation)
       
        # Uses final cut as bridge. Cancel = 0 Experimental. 
        bridge_height = 0
        if bridge_height:
            start_final_cut = (rs.CurveStartPoint(planar_plunge_crv)[0],rs.CurveStartPoint(planar_plunge_crv)[1],z_level)
            up_final_cut = rs.AddLine(start_final_cut,(start_final_cut[0],start_final_cut[1],z_level+bridge_height))
            rs.ObjectColor(up_final_cut,self.color_palette["cut"])
            curves_cut_path.append(up_final_cut)

        final_cut_translation = rs.VectorAdd((0,0,0),(0,0,z_level+bridge_height))
        final_cut = rs.CopyObject(planar_plunge_crv,final_cut_translation)
        
        rs.ObjectColor(final_cut,self.color_palette["cut"])
        curves_cut_path.append(final_cut)
        
        #adds finishing pass
        if finish_pass:
            finish_cut_curve = rs.CopyObject(main_crv,translation)
            rs.CurveSeam(finish_cut_curve,rs.CurveClosestPoint(finish_cut_curve , rs.CurveEndPoint(final_cut)))
            in_finish_curve = rs.AddLine(rs.CurveEndPoint(final_cut),rs.CurveEndPoint(finish_cut_curve))
            out_finish_curve = rs.AddLine(rs.CurveEndPoint(finish_cut_curve),rs.CurveEndPoint(final_cut))
            rs.ObjectColor(in_finish_curve,self.color_palette["cut"])
            rs.ObjectColor(out_finish_curve,self.color_palette["cut"])
            rs.ObjectColor(finish_cut_curve,self.color_palette["cut"])
            curves_cut_path.append(in_finish_curve)
            curves_cut_path.append(finish_cut_curve)
            curves_cut_path.append(out_finish_curve)
         
        #adds cutter output
        final_point = rs.CurveEndPoint(final_cut)
        out_curve = rs.AddLine(final_point,(final_point[0],final_point[1],sec_plane))
        rs.ObjectColor(out_curve,self.color_palette["rapid"])
        curves_cut_path.append(out_curve)
        
        rs.DeleteObjects([planar_plunge_crv,plunge_crv,cut_crv,crv,main_crv])
        
        #Deletes pocketing curves at level zero that are only used for copying
        if self.pocketing and not omit_box and pocketing_crvs:
            if self.input_data["circular_pocketing"]:
                for p in pocketing_crvs:
                    if p:
                        rs.DeleteObjects(p)
            else:
                for p in pocketing_crvs:
                    if p != 'sec_plane': rs.DeleteObject(p)
        
        return curves_cut_path
    
    def pocket_path_offset(self,z_level,translation,pocket_list):
        
        revised_list = []
        last_obj = None
        for obj in pocket_list:
            
            if obj != "sec_plane":
                revised_list.append(rs.CopyObject(obj,translation))
            else:
                if last_obj != obj:
                    revised_list.append(obj)
            last_obj = obj
        pocket_list = revised_list
        for i in range(0,len(pocket_list)):
            crv = pocket_list[i]
            if crv == "sec_plane": #Intermediate shift
                pep = rs.CurveEndPoint(pocket_list[i-1])
                try:
                    nsp = rs.CurveStartPoint(pocket_list[i+1])
                except:
                    
                    npt = rs.CurveStartPoint(self.cut_curve)
                    nsp = (npt[0],npt[1],z_level)
                   
                points = [rs.CurveEndPoint(pocket_list[i-1]),(pep[0],pep[1],self.general_input["sec_plane"]),(nsp[0],nsp[1],self.general_input["sec_plane"]),nsp]
                travel_line = rs.AddPolyline(points)
                rs.ObjectColor(travel_line,self.color_palette["cut"])
                pocket_list[i] = travel_line
                        
        return pocket_list
            
    def find_point_in_curve(self,crv):
        offset_points = rs.BoundingBox(crv)
        diagonal = rs.AddLine(offset_points[0],offset_points[2])
        test_points = rs.DivideCurveLength(diagonal,self.general_input['tolerance'],create_points=False, return_points=True)
        rs.DeleteObject(diagonal)
        for point in test_points:
            if rs.PointInPlanarClosedCurve(point,crv):
                return point
        return self.point
    
    def get_cut_curve(self,compensation=False,offset_distance=False,nurbs_curve=False):
        
        nurbs_curve = self.nurbs_curve if not nurbs_curve else nurbs_curve
        offset_distance = self.general_input["cut_diam"] * 0.5  if not offset_distance else offset_distance
        compensation = self.compensation if not compensation else compensation
        
        if compensation == 0: return rs.CopyObject(nurbs_curve)
        
        scl_obj = rs.ScaleObject(nurbs_curve,self.point,(1.2,1.2,1),True)
        offset_points = rs.BoundingBox(scl_obj)
        rs.DeleteObject(scl_obj)

        offset_point_a = offset_points[0]
        offset_point_b = self.point
        if not rs.PointInPlanarClosedCurve(self.point,nurbs_curve): offset_point_b = self.find_point_in_curve(nurbs_curve)
        offset_a = rs.OffsetCurve(nurbs_curve,offset_point_a,offset_distance,None,2)
        offset_b = rs.OffsetCurve(nurbs_curve,offset_point_b,offset_distance,None,2)

        #Check if the offset did not generate separate curves and if so, assign the original curve as a comparative offset.
        if not offset_a or len(offset_a) != 1:
            if offset_a: rs.DeleteObjects(offset_a)
            offset_a = rs.CopyObject(nurbs_curve)
            
        if not offset_b or len(offset_b) != 1:
            if offset_b: rs.DeleteObjects(offset_b)  
            offset_b = rs.CopyObject(nurbs_curve)
                
        #Check the area for internal or external offset.
        if rs.CurveArea(offset_a) < rs.CurveArea(offset_b):
            in_offset = offset_a
            out_offset = offset_b
        else:
            in_offset = offset_b
            out_offset = offset_a
        #Respond depending on what compensation is needed
        if compensation == 1:
            rs.DeleteObject(in_offset)
            #Gives orientation of the curve depending on the cutter rotation
            if rs.ClosedCurveOrientation(out_offset, direction=(0,0,1)) == -1:
                rs.ReverseCurve(out_offset)
            return out_offset
        elif compensation == -1:
            rs.DeleteObject(out_offset)
            #Gives orientation of the curve depending on the cutter rotation
            if rs.ClosedCurveOrientation(in_offset, direction=(0,0,1)) == 1:
                rs.ReverseCurve(in_offset)
            return in_offset
        else:
            rs.DeleteObject(in_offset)
            rs.DeleteObject(out_offset)
            return None


# The script that will be using the dialog.
def Main():
    
    #if not check_language_and_conditions(): return
    
    #Starts UI
    if sc.sticky.has_key(COMMAND_NAME):
        return
    
    #machining_settings,general_settings,user_data,postprocessors,machining_input,objects = initialize()
    
    # Create and show form
    form = camDialog()
    if not form.Initialize(PLUGIN_NAME,COMMAND_NAME,VERSION,WEBPAGE): return
    form.Owner = Rhino.UI.RhinoEtoApp.MainWindow
    form.Show()
    # Add the form to the sticky dictionary so it
    # survives when the main function ends.
    sc.sticky[COMMAND_NAME] = form
    return form
    


if __name__ == "__main__":

    Main()
   
    
