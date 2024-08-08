from datetime import datetime, timedelta, UTC
import logging

from flask_app.services.SupabaseService import SupabaseService
from flask_app.services.HelperService import HelperService
from flask_app.services.AuthService import AuthService

class RatelimitService():

    @staticmethod
    def sort_into_time_buckets(rate_limits):
        if not rate_limits:
            return {'monthly': 0, 'weekly': 0, 'daily': 0, 'minute': 0}
        
        now = datetime.now(UTC)
        month_start = now - timedelta(days=30)
        week_start = now - timedelta(days=7)
        day_start = now - timedelta(hours=24)
        minute_start = now - timedelta(minutes=1)

        logging.info(f'Rate limits: {rate_limits}')

        logging.info(f"month_start: {month_start}, week_start: {week_start}, day_start: {day_start}, minute_start: {minute_start}")
        logging.info(f"now: {now}")

        for item in rate_limits:
            item['created_at'] = datetime.fromisoformat(item['created_at']).replace(tzinfo=UTC)

        # Calculate counts for each time period
        monthly_count = sum(item['count'] for item in rate_limits if item['created_at'] >= month_start)
        weekly_count = sum(item['count'] for item in rate_limits if item['created_at'] >= week_start)
        daily_count = sum(item['count'] for item in rate_limits if item['created_at'] >= day_start)
        minute_count = sum(item['count'] for item in rate_limits if item['created_at'] >= minute_start)

        return {
            'monthly': monthly_count,
            'weekly': weekly_count,
            'daily': daily_count,
            'minute': minute_count
        }

    @staticmethod
    def is_rate_limited(userId, type):
        if AuthService.is_super_admin(user_id=userId):
            return False

        try:
            user_type = SupabaseService.get_user_type(userId=userId)

            current_usage = SupabaseService.get_rate_limit(userId=userId, type=type, userType=user_type)

            usage_dict = RatelimitService.sort_into_time_buckets(rate_limits=current_usage)

            rate_limits = SupabaseService.get_rate_limit_values(type=type, userType=user_type)

            if not rate_limits:
                logging.error(f'No rate limits found for userId: {userId}, rate_limits: {rate_limits}')
                return True
            
            rate_limits_dict = rate_limits[0]
            
            logging.info(f'Usage dict: {usage_dict}')
            logging.info(f'Rate limits: {rate_limits_dict}')
            
            return (
                usage_dict['monthly'] >= rate_limits_dict['monthly'] or
                usage_dict['weekly'] >= rate_limits_dict['weekly'] or
                usage_dict['daily'] >= rate_limits_dict['daily'] or
                usage_dict['minute'] >= rate_limits_dict['minute']
            )
        except Exception as e:
            logging.exception(f'Exception in is_rate_limited: {e}')
            return True
    
    @staticmethod
    def add_rate_limit(userId, type, value):
        if not HelperService.validate_all_uuid4(userId):
            logging.error(f'Invalid userId: {userId}')
            return None
        
        user_type = SupabaseService.get_user_type(userId=userId)
        
        ratelimit = SupabaseService.add_rate_limit(
            userId=userId,
            type=type,
            count=value,
            userType=user_type
        )

        if not ratelimit:
            return False
        
        return ratelimit[0]['id']

    @staticmethod
    def remove_rate_limit(rateLimitId):
        try:
            if not HelperService.validate_all_uuid4(rateLimitId):
                logging.error(f'Invalid rateLimitId: {rateLimitId}')
                return None
            
            SupabaseService.delete_rate_limit(rateLimitId)
        except Exception as e:
            logging.exception(f'Exception in remove_rate_limit wuth rateLimitId: {rateLimitId}, Exception: {e}')
            return None