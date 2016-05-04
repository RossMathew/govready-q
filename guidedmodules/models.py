from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings

from jsonfield import JSONField

class Project(models.Model):
    title = models.CharField(max_length=256, help_text="The title of this Project.")
    notes = models.TextField(blank=True, help_text="Notes about this Project for Project members.")

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)
    extra = JSONField(blank=True, help_text="Additional information stored with this object.")

    def get_absolute_url(self):
        from django.utils.text import slugify
        return "/tasks/projects/%d/%s" % (self.id, slugify(self.title))

class ProjectMembership(models.Model):
    project = models.ForeignKey(Project, related_name="members", help_text="The Project this is defining membership for.")
    user = models.ForeignKey(User, help_text="The user that is a member of the Project.")
    is_admin = models.BooleanField(default=False, help_text="Is the user an administrator of the Project?")
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
    	unique_together = [('project', 'user')]

class Task(models.Model):
    project = models.ForeignKey(Project, blank=True, null=True, help_text="The Project that this Task is a part of, or empty for Tasks that are just directly owned by the user.")
    editor = models.ForeignKey(User, help_text="The user that has primary responsibility for completing this Task.")
    module_id = models.CharField(max_length=128, help_text="The ID of the module being completed.")

    title = models.CharField(max_length=256, help_text="The title of this Task. If the user is performing multiple tasks for the same module, this title would distiguish the tasks.")
    notes = models.TextField(blank=True, help_text="Notes set by the user about why they are completing this task.")

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)
    extra = JSONField(blank=True, help_text="Additional information stored with this object.")

    class Meta:
        index_together = [
            ('project', 'editor', 'module_id'),
        ]

    @staticmethod
    def has_completed_task(user, module_id, project=None):
        task = Task.objects.filter(project=project, editor=user, module_id=module_id).first()
        if task is None:
            return False
        return task.is_finished()

    @staticmethod
    def get_task_for_module(user, module_id):
        # Gets a task given a module_id. Use only with system modules
        # where a user can only have one Task for the module.
        task, isnew = Task.objects.get_or_create(
            editor=user,
            module_id=module_id)
        if isnew:
            task.title = task.load_module().title
            task.save()
        return task

    def get_absolute_url(self):
        from django.utils.text import slugify
        return "/tasks/%d/%s" % (self.id, slugify(self.title))

    def load_module(self):
        from questions import Module
        return Module.load(self.module_id)

    def get_answers_dict(self):
        m = self.load_module()
        answered = { }
        for q in self.answers.all():
            answered[q.question_id] = q.value

            # If this question type is "module", its answer value is the dict
            # returned by get_answers_dict on the Task that is the answer to
            # the question.
            if m.questions_by_id[q.question_id].type == "module":
                answered[q.question_id] = q.answered_by_task.get_answers_dict()
        return answered

    def is_finished(self):
        return self.load_module().next_question(self.get_answers_dict()) == None

    def get_status_display(self):
        if not self.is_finished():
            return "In Progress, last edit " + self.updated.strftime("%x %X")
        else:
            return "Finished on " + self.updated.strftime("%x %X")

    def get_output(self):
        return self.load_module().render_output(self.get_answers_dict())

class Answer(models.Model):
    task = models.ForeignKey(Task, related_name="answers", help_text="The Task that this Answer is for.")
    question_id = models.CharField(max_length=128, help_text="The ID of the question (with the Task's module) that this Answer answers.")

    value = JSONField(blank=True, help_text="The actual answer value for the Question, or None/null if the question is not really answered yet.")
    answered_by_task = models.ForeignKey(Task, blank=True, null=True, related_name="is_answer_of", help_text="A Task that supplies the answer for this question.")

    notes = models.TextField(blank=True, help_text="Notes entered by the user completing this Answer.")

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)
    extra = JSONField(blank=True, help_text="Additional information stored with this object.")

    class Meta:
        unique_together = [('task', 'question_id')]

class Discussion(models.Model):
    project = models.ForeignKey(Project, help_text="The Project that this Discussion exists within.")
    for_answer = models.ForeignKey(Answer, help_text="The Answer that this discussion thread is for.")

    external_participants = models.ManyToManyField(User, blank=True, help_text="Additional Users who are participating in this chat, besides those that are members of the Project that contains the Discussion.")

    @property
    def title(self):
        return repr(self.for_answer)

    def is_participant(self, user):
        return (ProjectMembership.objects.filter(project=self.project, user=user)) \
            or (user in self.external_participants)

class Comment(models.Model):
    discussion = models.ForeignKey(Discussion, help_text="The Discussion that this comment is attached to.")
    replies_to = models.ForeignKey('self', related_name="replies", help_text="If this is a reply to a Comment, the Comment that this is in reply to.")
    user = models.ForeignKey(User, help_text="The user making a comment.")

    emojis = models.CharField(max_length=256, blank=True, null=True, help_text="A comma-separated list of emoji names that the user is reacting with.")
    text = models.TextField(blank=True, help_text="The text of the user's comment.")
    proposed_answer = JSONField(blank=True, null=True, help_text="A proposed answer to the question that this discussion is about.")

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)
    extra = JSONField(blank=True, help_text="Additional information stored with this object.")

    class Meta:
        index_together = [
            ('discussion', 'user'),
        ]

class Invitation(models.Model):
    # who is sending the invitation
    from_user = models.ForeignKey(User, related_name="invitations_sent", help_text="The User who sent the invitation.")
    from_project = models.ForeignKey(Project, related_name="invitations_sent", help_text="The Project within which the invitation exists.")
    
    # about what prompted the invitation
    prompt_task = models.ForeignKey(Task, blank=True, null=True, related_name="invitations_prompted", help_text="The Task that prompted the invitation.")
    prompt_question_id = models.CharField(max_length=64, blank=True, null=True, help_text="The ID of the question that prompted the invitation.")

    # what is the recipient being invited to?
    into_project = models.BooleanField(default=False, help_text="Whether the user being invited is being invited to join from_project.")
    into_new_task_module_id = models.CharField(max_length=128, blank=True, null=True, help_text="The ID of the module that the recipient is being asked to complete, if any.")
    into_task_editorship = models.ForeignKey(Task, blank=True, null=True, related_name="invitations_to_take_over", help_text="The Task that the recipient is being invited to take editorship over, if any.")
    into_discussion = models.ForeignKey(Discussion, blank=True, null=True, related_name="invitations", help_text="The Discussion that the recipient is being invited to join, if any.")

    # who is the recipient of the invitation?
    to_user = models.ForeignKey(User, related_name="invitations_received", blank=True, null=True, help_text="The user who the invitation was sent to, if to an existing user.")
    to_email = models.CharField(max_length=256, blank=True, null=True, help_text="The email address the invitation was sent to, if to a non-existing user.")

    # personalization
    text = models.TextField(blank=True, help_text="The personalized text of the invitation.")

    # what state is this invitation in?
    sent_at = models.DateTimeField(blank=True, null=True, help_text="If the invitation has been sent by email, when it was sent.")
    accepted_at = models.DateTimeField(blank=True, null=True, help_text="If the invitation has been accepted, when it was accepted.")
    revoked_at = models.DateTimeField(blank=True, null=True, help_text="If the invitation has been revoked, when it was revoked.")

    # what resulted from this invitation?
    accepted_user = models.ForeignKey(User, related_name="invitations_accepted", blank=True, null=True, help_text="The user that accepted the invitation (i.e. if the invitation was by email address and an account was created).")
    accepted_task = models.ForeignKey(Task, related_name="invitations_received", blank=True, null=True, help_text="The Task generated by accepting the invitation.")

    # random string to generate unique code for recipient
    email_invitation_code = models.CharField(max_length=64, blank=True, help_text="For emails, a unique verification code.")

    # bookkeeping
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, db_index=True)
    extra = JSONField(blank=True, help_text="Additional information stored with this object.")

    @staticmethod
    def create(from_task, from_question_id, to_user, to_email, text, add_to_project):
        return Invitation.objects.create(
            from_user = from_task.user,
            from_task = from_task,
            question_id = from_question_id,
            to_user = to_user,
            to_email = to_email,
            text = text,
            invite_to_project = from_task.project if add_to_project else None,
            email_invitation_code = Invitation.generate_email_invitation_code(),
        )

    @staticmethod
    def generate_email_invitation_code():
        import random, string
        return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(24))

    def get_acceptance_url(self):
        from django.core.urlresolvers import reverse
        return settings.SITE_ROOT_URL \
            + reverse('accept_invitation', kwargs={'code': self.email_invitation_code})

    def send(self):
        # Send and mark as sent.
        from htmlemailer import send_mail
        send_mail(
            "email/invitation",
            "GovReady Q <q@mg.govready.com>",
            [self.to_user.email if self.to_user else self.to_email],
            {
                'invitation': self,
            }
        )
        Invitation.objects.filter(id=self.id).update(sent_at=timezone.now())

    def is_expired(self):
        from datetime import timedelta
        return timezone.now() > (self.sent_at + timedelta(days=10))
    is_expired.boolean = True

    def accept(self, request):
        from django.contrib.auth import authenticate, login, logout
        from django.contrib import messages
        import urllib.parse

        # If this is a repeat-click, just redirect the user to where
        # they went the first time.
        if self.accepted_at:
            return self.accepted_task.get_absolute_url()

        # Can't accept if this object has expired. Warn the user but
        # send them to the homepage.
        if self.is_expired() or self.revoked_at:
            messages.add_message(request, messages.ERROR, 'The invitation you wanted to accept has expired.')
            return "/"

        # Get the user logged into an account.
        
        matched_user = self.to_user \
            or User.objects.filter(email=self.to_email).exclude(id=self.from_user.id).first()
        
        if self.to_user and request.user == self.to_user:
            # If the invitation was to a user account, and the user is already logged
            # in to it, then we're all set.
            pass

        elif matched_user:
            # If the invitation was to a user account or to an email address that has
            # an account, the user on this request has just demonstrated ownership of
            # that user's email address, so we can log them in immediately.
            matched_user = authenticate(user_object=matched_user)
            if not matched_user.is_active:
                messages.add_message(request, messages.ERROR, 'Your account has been deactivated.')
                return "/"
            if request.user.is_authenticated():
                # The user was logged into a different account before. Log them out
                # of that account and then log them into the account in the invitation.
                logout(request) # setting a message after logout but before login should keep the message in the session
                messages.add_message(request, messages.INFO, 'You have been logged in as %s.' % matched_user)
            login(request, matched_user)

        elif request.user.is_authenticated() and request.user != self.from_user:
            # The invitation was sent to an email address that does not have a matching
            # User account, but the user is already logged into an account --- continue
            # with that account.
            pass

        else:
            # The invitation was sent to an email address that does not have a matching
            # User account. Ask the user to log in or sign up, using a redirect to the
            # login page, with a next URL set to take them back to this step. In the
            # event the user was logged in (and we didn't handle it above), log them
            # out and force them to log into a new account.
            from django.core.urlresolvers import reverse
            logout(request)
            return reverse('account_signup') + "?next=" + urllib.parse.quote(self.get_acceptance_url())

        # The user is now logged in and able to accept the invitation.
        with transaction.atomic():

            redirect_to = "/"
            task = None

            # Add user to a project team.
            if self.into_project:
                ProjectMembership.objects.create(
                    project=self.from_project,
                    user=request.user,
                    )
                messages.add_message(request, messages.INFO, 'You have joined the team %s.' % self.from_project.title)

            # Create a new Task for the user to begin a module.
            if self.into_new_task_module_id:
                from questions import Module
                m = Module.load(self.into_new_task_module_id)
                task = Task.objects.create(
                    project=self.from_project,
                    user=request.user,
                    module_id=self.into_new_task_module_id,
                    title=m.title,
                )
                redirect_to = task.get_absolute_url()

            # Make this user the new editor of the Task.
            if self.into_task_editorship:
                # Sanity check: Is the user who sent the invitation still the editor?
                if self.into_task_editorship.editor != self.from_user:
                    messages.add_message(request, messages.ERROR, 'The invitation is no longer valid.')
                else:
                    # Make this user the new editor.
                    self.into_task_editorship.editor = request.user
                    self.into_task_editorship.save(update_fields=['editor'])
                    # TODO: Create a notification that the editor changed?
                    messages.add_message(request, messages.INFO, 'You are now the editor for module %s.' % self.into_task_editorship.title)
                    redirect_to = self.into_task_editorship.get_absolute_url()

            # Add this user into a discussion.
            if self.into_discussion:
                if self.into_discussion.is_participant(request.user):
                    # user is already a participant --- possibly because they were just invited
                    # and now added into the project, which gives them access to the discussion
                    # --- so just redirect to it.
                    pass
                else:
                    # add the user to the external_participants list for the discussion. 
                    self.into_discussion.external_participants.add(request.user)
                    messages.add_message(request, messages.INFO, 'You are now a participant in the discussion on %s.' % discussion.title)
                redirect_to = self.into_discussion.answer.get_absolute_url()

            # Update this invitation.
            Invitation.objects.filter(id=self.id).update(
                accepted_at=timezone.now(),
                accepted_user=request.user,
                accepted_task=task,
            )

            # TODO: Notify self.from_user that the invitation was accepted.
            #       Create other notifications?

            return redirect_to