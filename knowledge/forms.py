from django import forms

from .models import Article, Section


class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ['title', 'content', 'section', 'status', 'allow_comments']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['section'].queryset = Section.objects.filter(is_active=True)
        self.fields['section'].required = False
        self.fields['content'].required = True
