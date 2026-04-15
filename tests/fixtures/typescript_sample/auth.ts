import { User, Token, AuthResult } from './types';

export class AuthService {
    async authenticate(email: string, password: string): Promise<AuthResult> {
        const user = await this.findUser(email);
        if (!this.verifyPassword(user, password)) {
            throw new Error('Invalid credentials');
        }
        const token = await this.createToken(user);
        return { token, user };
    }

    private async findUser(email: string): Promise<User> {
        return { id: 1, email, hashedPassword: 'hash' };
    }

    private verifyPassword(user: User, plain: string): boolean {
        return user.hashedPassword === plain;
    }

    private async createToken(user: User): Promise<Token> {
        return { value: `tok_${user.email}`, userId: user.id };
    }

    async logout(tokenValue: string): Promise<void> {
        // invalidate token
    }
}
