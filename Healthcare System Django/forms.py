# accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.core.exceptions import ValidationError
from .models import User, UserProfile

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    phone_number = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    user_type = forms.ChoiceField(
        choices=[('patient', 'Patient'), ('doctor', 'Doctor')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    date_of_birth = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'phone_number', 
                  'user_type', 'date_of_birth', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs['class'] = 'form-control'
        self.fields['password2'].widget.attrs['class'] = 'form-control'
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email
    
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if phone and not phone.replace('+', '').replace('-', '').isdigit():
            raise ValidationError("Please enter a valid phone number.")
        return phone

class UserLoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Username or Email'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Password'
    }))

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 
                  'address', 'date_of_birth', 'profile_picture']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("A user with this email already exists.")
        return email

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['emergency_contact', 'blood_group', 'allergies', 'medical_history']
        widgets = {
            'emergency_contact': forms.TextInput(attrs={'class': 'form-control'}),
            'blood_group': forms.Select(attrs={'class': 'form-control'}, choices=[
                ('', 'Select Blood Group'),
                ('A+', 'A+'), ('A-', 'A-'),
                ('B+', 'B+'), ('B-', 'B-'),
                ('AB+', 'AB+'), ('AB-', 'AB-'),
                ('O+', 'O+'), ('O-', 'O-'),
            ]),
            'allergies': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'medical_history': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class CustomPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    new_password1 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    new_password2 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    
    # patients/forms.py
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import MedicalRecord, Appointment, LabTest, Prescription

class AppointmentForm(forms.ModelForm):
    appointment_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        help_text="Select a date (must be today or in the future)"
    )
    appointment_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        help_text="Select a time"
    )
    
    class Meta:
        model = Appointment
        fields = ['doctor', 'appointment_date', 'appointment_time', 'reason']
        widgets = {
            'doctor': forms.Select(attrs={'class': 'form-control'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 
                                           'placeholder': 'Describe your symptoms or reason for visit'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.patient = kwargs.pop('patient', None)
        super().__init__(*args, **kwargs)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.fields['doctor'].queryset = User.objects.filter(user_type='doctor', is_verified=True)
        self.fields['doctor'].label_from_instance = lambda obj: f"Dr. {obj.get_full_name()}"
    
    def clean_appointment_date(self):
        date = self.cleaned_data.get('appointment_date')
        if date and date < timezone.now().date():
            raise ValidationError("Appointment date cannot be in the past.")
        return date
    
    def clean(self):
        cleaned_data = super().clean()
        doctor = cleaned_data.get('doctor')
        date = cleaned_data.get('appointment_date')
        time = cleaned_data.get('appointment_time')
        
        if doctor and date and time:
            if Appointment.objects.filter(
                doctor=doctor, 
                appointment_date=date, 
                appointment_time=time,
                status__in=['pending', 'scheduled', 'confirmed']
            ).exists():
                raise ValidationError("This time slot is already booked. Please choose another time.")
        
        return cleaned_data

class MedicalRecordForm(forms.ModelForm):
    class Meta:
        model = MedicalRecord
        fields = ['diagnosis', 'treatment', 'prescription', 'lab_results', 'notes', 'attachment']
        widgets = {
            'diagnosis': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'treatment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'prescription': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'lab_results': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
        }

class LabTestForm(forms.ModelForm):
    class Meta:
        model = LabTest
        fields = ['test_name', 'test_description']
        widgets = {
            'test_name': forms.TextInput(attrs={'class': 'form-control'}),
            'test_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class LabResultForm(forms.ModelForm):
    class Meta:
        model = LabTest
        fields = ['result', 'result_file', 'status']
        widgets = {
            'result': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'result_file': forms.FileInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

class PrescriptionForm(forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ['medications', 'dosage_instructions', 'duration']
        widgets = {
            'medications': forms.Textarea(attrs={'class': 'form-control', 'rows': 4,
                                                 'placeholder': 'List medications with dosages'}),
            'dosage_instructions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'duration': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 7 days'}),
        }