class TeachersSearchList(APIView):
    """
    API to list:
    - all teachers for subject and grade with details (if no any specific teacher is selected) 
    - any specific teacher for subject and grade with details (if any teacher is selected).
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        
        try:
            user = validate_logged_in_infyni_user(request)
            if not user:
                return generic_response(status.HTTP_400_BAD_REQUEST, "Access token is invalid")
            if not user.is_authenticated:
                return generic_response(status.HTTP_400_BAD_REQUEST, "User is not logged in")

            if user.is_instructor or user.is_homework_teacher():
                return generic_response(status.HTTP_400_BAD_REQUEST, "User is not a homework student")
            
            # getting subject and grade from params
            subject_id = request.GET.get("subject")
            grade_id = request.GET.get("grade")
            teacher = request.GET.get("teacher")
            teacher_id = request.GET.get("teacher_id")
            language_id =  request.GET.get("language_id")
            rating = request.GET.get("rating")

            # Check if both subject_id and grade_id are provided
            if not subject_id or not grade_id:
                return generic_response(status.HTTP_400_BAD_REQUEST, "Please provide both subject_id and grade_id.")

            # Filter by subject and grade
            homework_teachers = HomeworkTeacher.objects.filter(subjects=subject_id, subjects__grade__id=grade_id)

            # If teacher_id is provided, filter by teacher_id
            if teacher_id:
                homework_teachers = homework_teachers.filter(id=teacher_id).first()
                if not homework_teachers:
                    return generic_response(status.HTTP_404_NOT_FOUND, "Teacher not found")

                # Serialize single teacher without many=True
                serialized_data = TeacherListingUnderGradeAndSubjectSerializer(
                    homework_teachers
                ).data

                return generic_response(status.HTTP_200_OK, data=[serialized_data])
            else:
                # Annotate full name for teacher name filtering
                homework_teachers = homework_teachers.annotate(
                    full_name=Concat('user__first_name', Value(' '), 'user__last_name', output_field=CharField())
                )
                
                # If teacher name is provided, filter by full_name, first_name, or last_name
                if teacher:
                    homework_teachers = homework_teachers.filter(
                        Q(
                            Q(full_name__icontains=teacher) |
                            Q(user__first_name__icontains=teacher) |
                            Q(user__last_name__icontains=teacher)
                        )
                    )

                # If language_id is provided, prioritize teachers with the language, and then others
                if language_id:

                    # Create an Exists subquery to check if the language exists for the teacher
                    language_exists = HomeworkTeacher.objects.filter(
                        id=OuterRef('id'),
                        language__id=language_id,
                    )

                    # Annotate the queryset with the exists condition
                    homework_teachers = homework_teachers.annotate(
                        has_language=Exists(language_exists)
                    ).annotate(
                        has_language_flag=Case(
                            When(has_language=True, then=True),
                            default=False,
                            output_field=BooleanField(),
                        )
                    ).order_by('-has_language_flag', 'full_name')

                else:
                    # If no language filtering is required, just order by full name
                    homework_teachers = homework_teachers.order_by('full_name')
                
                serialized_data = TeacherListingUnderGradeAndSubjectSerializer(
                    homework_teachers, many=True
                ).data

               # Filter by rating if provided
                if rating:
                    # Convert rating to a float and round it to the nearest integer
                    try:
                        rating = round(float(rating))
                    except ValueError:
                        return generic_response(status.HTTP_400_BAD_REQUEST, "Invalid rating value")

                    # Annotate with average rating from TeacherFeedback model
                    homework_teachers = homework_teachers.annotate(
                        avg_rating=Avg('teacherfeedback__rating')  # Annotate with average rating from TeacherFeedback model
                    ).filter(avg_rating__gte=rating)

                # Serialize the filtered data
                serialized_data = TeacherListingUnderGradeAndSubjectSerializer(
                    homework_teachers, many=True
                ).data

               
                # Return teacher listing
                return get_pure_paginated_response(serialized_data, request)
        
        except Exception as e:
            print(f"An error occurred while listing teachers: {e}")
            logger.debug(f"An error occurred while listing teachers: {e}")

            return generic_response(
                status.HTTP_400_BAD_REQUEST, "An error occurred while listing teachers"
            )
