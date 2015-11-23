__author__ = 'zak'
from django.contrib.auth.models import User
from clatoolkit.models import UserProfile, UnitOffering, GroupMap


################################
# Assigns Entire Class to Groups
################################
def assign_groups_class(courseCode, max_size=5):
    course_qs = UnitOffering.objects.filter(code = '%s' % courseCode)

    course_users = User.objects.filter(usersinunitoffering__in=course_qs)

    #print(course_users)

    group_n = 1
    max_grp_size = max_size
    group = []

    for index in range(1,(len(course_users)+1)): #range from 1 - n; instead of 0-n
        try:
            e = UserProfile.objects.filter(user=course_users[index-1])[0]
            group.append((e, group_n))
        except Exception as e:
            print(e)

        if (index%max_grp_size is 0):
            group_n = group_n+1

    #print(group)

    for (user, group_id) in group:
        g = GroupMap(userId=user, course_code=courseCode, groupId=group_id)
        g.save()
        print("Mapped UserId: "+str(user.id)+" in course: "+str(courseCode)+" to group "+str(group_id));






################################
# Called on User Registration to assign group
################################
#def assign_user_on_register(userprofile, course_code, groupmap_qs):



#####
# Code Graveyard
#####
"""

    max_group_size = max_size

    cursor = connection.cursor()
    cursor.execute(""SELECT clatoolkit_unitoffering.id
                   FROM clatoolkit_unitoffering
                   WHERE clatoolkit_unitoffering.code ='%s';""
                   % (course_code))

    unit_id = cursor.fetchall()

    cursor.execute(""SELECT clatoolkit_unitoffering_users.user_id
                    FROM clatoolkit_unitoffering_users
                    WHERE clatoolkit_unitoffering_users.unitoffering_id = '%s';""
                  % (unit_id[0]))

    users_id = cursor.fetchall()
    total = len(users_id)
    groups = []

    group = []
    for user_id in users_id:
        if len(group) < max_size:
            group.append(user_id[0])
        elif len(group) == max_size:
            groups.append(group)
            group = []
            group.append(user_id[0])

    group_num = 1

    sql_string = ""
                    UPDATE clatoolkit_userprofile
                    SET
                ""

    for g in groups:


"""