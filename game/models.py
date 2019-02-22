from django.db import models


class Round(models.Model):
    chat_id = models.BigIntegerField(primary_key=True)
    counter = models.IntegerField(default=0)
    message_id = models.BigIntegerField()

    def get_actors(self):
        actors = Actor.objects.filter(belong=self).order_by('value').reverse().all()
        return list(actors)


class Actor(models.Model):
    name = models.CharField(max_length=128)
    value = models.IntegerField()
    belong = models.ForeignKey(Round, on_delete=models.CASCADE)
