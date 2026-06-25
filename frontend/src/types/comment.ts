export interface CommentDTO {
  id: number;
  weibo_comment_id: string;
  user_uid: string;
  user_name: string;
  content: string;
  like_count: number;
  rank: number;
  is_hot: boolean;
  is_team_member: boolean;
  created_at?: string;
}
