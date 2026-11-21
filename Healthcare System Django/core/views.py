from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import CreateView, UpdateView, TemplateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from .models import User, UserProfile, ActivityLog
from .forms import (
    UserRegistrationForm, UserLoginForm, UserUpdateForm, 
    UserProfileForm, CustomPasswordChangeForm
)

class RegisterView(CreateView):
    model = User
    form_class = UserRegistrationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('accounts:login')
    
    def form_valid(self, form):
        user = form.save()
        UserProfile.objects.create(user=user)
        messages.success(self.request, 'Registration successful! Please login.')
        return super().form_valid(form)
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('accounts:dashboard')
        return super().dispatch(request, *args, **kwargs)

def login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                ActivityLog.objects.create(
                    user=user,
                    action='Logged in',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                messages.success(request, f'Welcome back, {user.first_name}!')
                return redirect('accounts:dashboard')
    else:
        form = UserLoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})

@login_required
def logout_view(request):
    ActivityLog.objects.create(
        user=request.user,
        action='Logged out',
        ip_address=request.META.get('REMOTE_ADDR')
    )
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('accounts:login')

@login_required
def dashboard_view(request):
    user = request.user
    context = {
        'user': user,
    }
    
    if user.user_type == 'patient':
        from patients.models import Appointment, MedicalRecord
        context['upcoming_appointments'] = Appointment.objects.filter(
            patient=user, status='scheduled'
        ).order_by('appointment_date')[:5]
        context['recent_records'] = MedicalRecord.objects.filter(
            patient=user
        ).order_by('-created_at')[:5]
    elif user.user_type == 'doctor':
        from patients.models import Appointment
        context['today_appointments'] = Appointment.objects.filter(
            doctor=user, appointment_date__date=timezone.now().date()
        ).order_by('appointment_time')
        context['pending_appointments'] = Appointment.objects.filter(
            doctor=user, status='pending'
        ).count()
    
    context['recent_activities'] = ActivityLog.objects.filter(
        user=user
    )[:10]
    
    return render(request, 'accounts/dashboard.html', context)

@login_required
def profile_view(request):
    user = request.user
    profile, created = UserProfile.objects.get_or_create(user=user)
    
    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, request.FILES, instance=user)
        profile_form = UserProfileForm(request.POST, instance=profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('accounts:profile')
    else:
        user_form = UserUpdateForm(instance=user)
        profile_form = UserProfileForm(instance=profile)
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
    }
    return render(request, 'accounts/profile.html', context)

@login_required
def change_password_view(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Password changed successfully!')
            return redirect('accounts:profile')
    else:
        form = CustomPasswordChangeForm(request.user)
    
    return render(request, 'accounts/change_password.html', {'form': form})

# patients/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from datetime import datetime
from .models import Appointment, MedicalRecord, LabTest, Prescription
from .forms import (
    AppointmentForm, MedicalRecordForm, LabTestForm, 
    LabResultForm, PrescriptionForm
)
from accounts.models import User

@login_required
def appointment_list(request):
    if request.user.user_type == 'patient':
        appointments = Appointment.objects.filter(patient=request.user)
    elif request.user.user_type == 'doctor':
        appointments = Appointment.objects.filter(doctor=request.user)
    else:
        appointments = Appointment.objects.all()
    
    status_filter = request.GET.get('status')
    if status_filter:
        appointments = appointments.filter(status=status_filter)
    
    paginator = Paginator(appointments, 10)
    page = request.GET.get('page')
    appointments = paginator.get_page(page)
    
    return render(request, 'patients/appointment_list.html', {
        'appointments': appointments,
        'status_filter': status_filter,
    })

@login_required
def appointment_create(request):
    if request.user.user_type != 'patient':
        messages.error(request, 'Only patients can book appointments.')
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
        form = AppointmentForm(request.POST, patient=request.user)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.patient = request.user
            appointment.save()
            messages.success(request, 'Appointment booked successfully!')
            return redirect('patients:appointment_list')
    else:
        form = AppointmentForm(patient=request.user)
    
    return render(request, 'patients/appointment_form.html', {'form': form})

@login_required
def appointment_detail(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    
    # Check permission
    if request.user != appointment.patient and request.user != appointment.doctor and request.user.user_type != 'admin':
        messages.error(request, 'You do not have permission to view this appointment.')
        return redirect('accounts:dashboard')
    
    return render(request, 'patients/appointment_detail.html', {'appointment': appointment})

@login_required
def appointment_update_status(request, pk, status):
    appointment = get_object_or_404(Appointment, pk=pk)
    
    if request.user != appointment.doctor and request.user.user_type != 'admin':
        messages.error(request, 'You do not have permission to update this appointment.')
        return redirect('accounts:dashboard')
    
    valid_statuses = [choice[0] for choice in Appointment.STATUS_CHOICES]
    if status in valid_statuses:
        appointment.status = status
        appointment.save()
        messages.success(request, f'Appointment status updated to {status}.')
    else:
        messages.error(request, 'Invalid status.')
    
    return redirect('patients:appointment_detail', pk=pk)

@login_required
def medical_record_list(request):
    if request.user.user_type == 'patient':
        records = MedicalRecord.objects.filter(patient=request.user)
    elif request.user.user_type == 'doctor':
        records = MedicalRecord.objects.filter(
            Q(doctor=request.user) | Q(patient__appointments__doctor=request.user)
        ).distinct()
    else:
        records = MedicalRecord.objects.all()
    
    # Search
    search_query = request.GET.get('search')
    if search_query:
        records = records.filter(
            Q(patient__first_name__icontains=search_query) |
            Q(patient__last_name__icontains=search_query) |
            Q(diagnosis__icontains=search_query)
        )
    
    paginator = Paginator(records, 10)
    page = request.GET.get('page')
    records = paginator.get_page(page)
    
    return render(request, 'patients/medical_record_list.html', {
        'records': records,
        'search_query': search_query,
    })

@login_required
def medical_record_create(request, patient_id):
    if request.user.user_type != 'doctor' and request.user.user_type != 'admin':
        messages.error(request, 'Only doctors can create medical records.')
        return redirect('accounts:dashboard')
    
    patient = get_object_or_404(User, pk=patient_id, user_type='patient')
    
    if request.method == 'POST':
        form = MedicalRecordForm(request.POST, request.FILES)
        if form.is_valid():
            record = form.save(commit=False)
            record.patient = patient
            record.doctor = request.user
            record.save()
            messages.success(request, 'Medical record created successfully!')
            return redirect('patients:medical_record_detail', pk=record.pk)
    else:
        form = MedicalRecordForm()
    
    return render(request, 'patients/medical_record_form.html', {
        'form': form,
        'patient': patient,
    })

@login_required
def medical_record_detail(request, pk):
    record = get_object_or_404(MedicalRecord, pk=pk)
    
    # Permission check
    if (request.user != record.patient and 
        request.user != record.doctor and 
        request.user.user_type != 'admin'):
        messages.error(request, 'You do not have permission to view this record.')
        return redirect('accounts:dashboard')
    
    return render(request, 'patients/medical_record_detail.html', {'record': record})

@login_required
def lab_test_list(request):
    if request.user.user_type == 'patient':
        tests = LabTest.objects.filter(patient=request.user)
    elif request.user.user_type == 'doctor':
        tests = LabTest.objects.filter(doctor=request.user)
    else:
        tests = LabTest.objects.all()
    
    return render(request, 'patients/lab_test_list.html', {'tests': tests})

@login_required
def lab_test_create(request, patient_id):
    if request.user.user_type != 'doctor' and request.user.user_type != 'admin':
        messages.error(request, 'Only doctors can order lab tests.')
        return redirect('accounts:dashboard')
    
    patient = get_object_or_404(User, pk=patient_id, user_type='patient')
    
    if request.method == 'POST':
        form = LabTestForm(request.POST)
        if form.is_valid():
            test = form.save(commit=False)
            test.patient = patient
            test.doctor = request.user
            test.save()
            messages.success(request, 'Lab test ordered successfully!')
            return redirect('patients:lab_test_list')
    else:
        form = LabTestForm()
    
    return render(request, 'patients/lab_test_form.html', {
        'form': form,
        'patient': patient,
    })

@login_required
def lab_test_update(request, pk):
    test = get_object_or_404(LabTest, pk=pk)
    
    if request.user.user_type != 'admin' and request.user != test.doctor:
        messages.error(request, 'You do not have permission to update this test.')
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
        form = LabResultForm(request.POST, request.FILES, instance=test)
        if form.is_valid():
            test = form.save(commit=False)
            if test.status == 'completed' and not test.completed_date:
                test.completed_date = timezone.now()
            test.save()
            messages.success(request, 'Lab test updated successfully!')
            return redirect('patients:lab_test_list')
    else:
        form = LabResultForm(instance=test)
    
    return render(request, 'patients/lab_test_form.html', {'form': form, 'test': test})

@login_required
def prescription_create(request, appointment_id):
    appointment = get_object_or_404(Appointment, pk=appointment_id)
    
    if request.user != appointment.doctor and request.user.user_type != 'admin':
        messages.error(request, 'You do not have permission to create prescriptions.')
        return redirect('accounts:dashboard')
    
    if hasattr(appointment, 'prescription'):
        messages.warning(request, 'A prescription already exists for this appointment.')
        return redirect('patients:appointment_detail', pk=appointment_id)
    
    if request.method == 'POST':
        form = PrescriptionForm(request.POST)
        if form.is_valid():
            prescription = form.save(commit=False)
            prescription.appointment = appointment
            prescription.save()
            messages.success(request, 'Prescription created successfully!')
            return redirect('patients:appointment_detail', pk=appointment_id)
    else:
        form = PrescriptionForm()
    
    return render(request, 'patients/prescription_form.html', {
        'form': form,
        'appointment': appointment,
    })