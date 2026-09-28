import 'package:flutter_test/flutter_test.dart';
import 'package:app/main.dart';

void main() {
  testWidgets('CocoCare home screen test', (WidgetTester tester) async {
    await tester.pumpWidget(const CocoCareApp());

    expect(find.text('CocoCare'), findsOneWidget);
    expect(find.text('Good morning'), findsOneWidget);
    expect(find.text('Your farm'), findsOneWidget);
    expect(find.text('Quick actions'), findsOneWidget);

    expect(find.text('Check your coconut'), findsOneWidget);
    expect(find.text('AI Assistant'), findsOneWidget);
    expect(find.text('Expenses'), findsOneWidget);
    expect(find.text('Find workers'), findsOneWidget);
    expect(find.text('Market price'), findsOneWidget);
  });
}